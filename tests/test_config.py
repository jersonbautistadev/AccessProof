import copy
import tomllib
import unittest

from accessproof.config import ConfigError, load_policy, parse_policy, path, target
from tests.support import ROOT, policy


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.raw = tomllib.loads((ROOT / "configs/demo.toml").read_text())

    def test_demo_is_complete_and_fingerprint_stable(self):
        first = parse_policy(self.raw)
        self.assertEqual(len(first.resources) * len(first.identities), 12)
        self.assertEqual(first.fingerprint, policy().fingerprint)
        self.raw["resources"].reverse()
        self.assertEqual(first.fingerprint, parse_policy(self.raw).fingerprint)

    def test_semantic_changes_change_fingerprint(self):
        original = policy().fingerprint
        for mutation in (
            lambda raw: raw.update(policy_version="2"),
            lambda raw: raw["resources"][0]["permissions"].update(bob="allow"),
            lambda raw: raw["resources"][0].update(path="/records/another"),
            lambda raw: raw["resources"][0]["allow"]["json_equals"].update({"/id": "changed"}),
        ):
            with self.subTest(mutation=mutation):
                raw = copy.deepcopy(self.raw)
                mutation(raw)
                self.assertNotEqual(original, parse_policy(raw).fingerprint)

    def test_rejects_nonlocal_or_ambiguous_targets(self):
        for url in ("https://example.com", "http://10.0.0.1", "http://localhost:8765", "http://127.0.0.1@evil.example",
                    "http://token@127.0.0.1", "ftp://127.0.0.1", "http://127.0.0.1/path", "http://127.0.0.1?secret=x",
                    "http://127.0.0.1:0", "http://127.0.0.1:70000", "http://[::1%25eth0]", "http://127.0.0.1/#"):
            with self.subTest(url=url), self.assertRaises(ConfigError):
                target({"base_url": url, "environment": "development"})
        self.assertEqual(target({"base_url": "https://[::1]:1234/", "environment": "test"}).address, ("::1", 1234, "https"))

    def test_rejects_redirect_style_paths_and_query_secrets(self):
        for endpoint in ("https://evil.example", "//127.0.0.1/", "/../admin", "/a/./b", "/a%2fb", "/a?token=x", "/a#b", "/a\\b", "/a\r\nX-Test:x"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ConfigError):
                path(endpoint)

    def test_rejects_policy_errors_without_echoing_values(self):
        mutations = (
            lambda raw: raw.update(schema_version=True),
            lambda raw: raw["target"].update(environment="production"),
            lambda raw: raw["target"].update(timeout_seconds=True),
            lambda raw: raw["target"].update(max_response_bytes=5),
            lambda raw: raw["identities"]["alice"].update(token="SHOULD_NOT_ECHO_THIS_VALUE"),
            lambda raw: raw["identities"]["alice"]["verify"]["json_equals"].pop("/subject"),
            lambda raw: raw["identities"]["bob"]["verify"]["json_equals"].update({"/subject": "alice"}),
            lambda raw: raw["identities"]["bob"].update(token_env="ACCESSPROOF_ALICE_TOKEN"),
            lambda raw: raw["resources"][0].update(method="POST"),
            lambda raw: raw["resources"][0].update(protected_paths=[]),
            lambda raw: raw["resources"][0].update(positive_identity="anonymous"),
            lambda raw: raw["resources"][0]["permissions"].update(unknown="allow"),
            lambda raw: raw["resources"][0]["permissions"].update(alice="deny"),
            lambda raw: raw["resources"][0]["allow"].update(json_equals={}),
            lambda raw: raw["resources"][0]["allow"].update(statuses=[403]),
            lambda raw: raw["resources"][0]["deny"].update(statuses=[500]),
            lambda raw: raw["resources"][0]["allow"].update(json_equals={"/bad~2": 1}),
            lambda raw: raw["resources"].append(raw["resources"][0]),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                raw = copy.deepcopy(self.raw)
                mutation(raw)
                with self.assertRaises(ConfigError) as captured:
                    parse_policy(raw)
                self.assertNotIn("SHOULD_NOT_ECHO_THIS_VALUE", str(captured.exception))

    def test_missing_config_is_actionable(self):
        with self.assertRaises(ConfigError):
            load_policy(ROOT / "does-not-exist.toml")
