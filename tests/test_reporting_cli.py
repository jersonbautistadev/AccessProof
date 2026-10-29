import contextlib
import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from accessproof.__main__ import main
from accessproof.config import ConfigError
from accessproof.reporting import compare, load_baseline, render_html, sanitize, terminal, write_reports
from accessproof.runner import gate_failed, run
from tests.support import ENVIRONMENT, FixtureTransport, ROOT, TOKENS, policy, running_demo


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.clean = run(policy(), environment=ENVIRONMENT, transport=FixtureTransport())

    def test_equivalent_baseline_highlights_new_failure_and_recovery(self):
        regression = copy.deepcopy(self.clean)
        target = next(row for row in regression["results"] if row["id"] == "permission:bob-record:alice")
        target["status"] = "failed"
        compare(regression, self.clean)
        self.assertEqual(regression["comparison"]["newly_failing"], [target["id"]])
        self.assertTrue(gate_failed(regression))
        recovered = copy.deepcopy(self.clean)
        compare(recovered, regression)
        self.assertEqual(recovered["comparison"]["resolved"], [target["id"]])
        self.assertFalse(gate_failed(recovered))

    def test_inconclusive_regressions_are_visible_and_block(self):
        current = copy.deepcopy(self.clean)
        current["results"][-1]["status"] = "inconclusive"
        compare(current, self.clean)
        self.assertEqual(current["comparison"]["newly_inconclusive"], [current["results"][-1]["id"]])
        self.assertTrue(gate_failed(current))

    def test_policy_change_blocks_even_if_all_current_checks_pass(self):
        current = run(replace(policy(), policy_version="2"), environment=ENVIRONMENT, transport=FixtureTransport())
        compare(current, self.clean)
        self.assertEqual(current["summary"], {"passed": 18})
        self.assertEqual(current["comparison"]["status"], "policy_changed")
        self.assertTrue(gate_failed(current))

    def test_missing_baseline_rows_cannot_be_silently_equivalent(self):
        baseline = copy.deepcopy(self.clean)
        removed = baseline["results"].pop()
        compare(self.clean, baseline)
        self.assertEqual(self.clean["comparison"]["status"], "coverage_mismatch")
        self.assertIn(removed["id"], self.clean["comparison"]["added"])
        self.assertTrue(gate_failed(self.clean))

    def test_reports_never_contain_response_values_or_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            safe = sanitize(self.clean, list(TOKENS.values()))
            write_reports(safe, directory)
            for filename in ("report.json", "report.html"):
                text = (Path(directory) / filename).read_text()
                for secret in [*TOKENS.values(), "SYNTHETIC_ALICE_PRIVATE_NOTE", "SYNTHETIC_BOB_PRIVATE_NOTE", "synthetic-login"]:
                    self.assertNotIn(secret, text)
            self.assertEqual(load_baseline(Path(directory) / "report.json")["policy_fingerprint"], self.clean["policy_fingerprint"])

    def test_html_escapes_metadata_and_redacts_literal_secrets(self):
        self.clean["results"][0]["evidence"]["skip_reason"] = '<script>alert("x")</script> ' + TOKENS["alice"] + "\x1b[31m"
        safe = sanitize(self.clean, list(TOKENS.values()))
        html = render_html(safe)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn(TOKENS["alice"], html)
        self.assertNotIn("\x1b", terminal(safe))
        self.assertIn("Content-Security-Policy", html)

    def test_invalid_token_values_do_not_corrupt_engine_owned_schema(self):
        safe = sanitize(self.clean, ["status", "passed", "not_requested"])
        self.assertEqual(safe["results"][0]["status"], "passed")
        self.assertFalse(gate_failed(safe))

    def test_bad_baselines_fail_closed(self):
        for mutation in (
            lambda raw: raw.update(report_version=2),
            lambda raw: raw.update(evaluator_version=999),
            lambda raw: raw.update(policy_fingerprint="bad"),
            lambda raw: raw["results"].append(raw["results"][0]),
            lambda raw: raw["results"][0].update(status=[]),
            lambda raw: raw.update(results=[]),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                raw = copy.deepcopy(self.clean)
                mutation(raw)
                filename = Path(directory) / "baseline.json"
                filename.write_text(json.dumps(raw))
                with self.assertRaises(ConfigError):
                    load_baseline(filename)


class CliTests(unittest.TestCase):
    def invoke(self, arguments, environment=ENVIRONMENT):
        output, error = io.StringIO(), io.StringIO()
        with patch.dict("os.environ", environment, clear=True), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = main(arguments)
        return code, output.getvalue(), error.getvalue()

    def local_config(self, directory, configured):
        text = (ROOT / "configs/demo.toml").read_text().replace("http://127.0.0.1:8765", configured.target.base_url)
        filename = Path(directory) / "policy.toml"
        filename.write_text(text)
        return str(filename)

    def test_cli_fixed_exit_zero_and_vulnerable_exit_one(self):
        for mode, expected in (("fixed", 0), ("vulnerable", 1)):
            with self.subTest(mode=mode), running_demo(mode) as configured, tempfile.TemporaryDirectory() as directory:
                code, output, error = self.invoke(["run", self.local_config(directory, configured), "--out", str(Path(directory) / "reports")])
                self.assertEqual(code, expected, error)
                self.assertEqual(error, "")
                for token in TOKENS.values():
                    self.assertNotIn(token, output)
                self.assertTrue((Path(directory) / "reports/report.html").exists())

    def test_cli_missing_credentials_exit_one_with_report(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output, error = self.invoke(["run", str(ROOT / "configs/demo.toml"), "--out", directory], environment={})
            self.assertEqual(code, 1)
            self.assertIn("credential_missing", output)
            self.assertTrue((Path(directory) / "report.json").exists())

    def test_cli_configuration_errors_exit_two(self):
        code, _, error = self.invoke(["run", "nonexistent.toml"])
        self.assertEqual(code, 2)
        self.assertIn("configuration error", error)

    def test_cli_does_not_overwrite_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run(policy(), environment=ENVIRONMENT, transport=FixtureTransport())
            write_reports(report, directory)
            filename = Path(directory) / "report.json"
            original = filename.read_bytes()
            code, _, _ = self.invoke(["run", str(ROOT / "configs/demo.toml"), "--baseline", str(filename), "--out", directory])
            self.assertEqual(code, 2)
            self.assertEqual(filename.read_bytes(), original)

    def test_baseline_is_preserved_even_when_named_like_html_output(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run(policy(), environment=ENVIRONMENT, transport=FixtureTransport())
            filename = Path(directory) / "report.html"
            original = json.dumps(report).encode()
            filename.write_bytes(original)
            code, _, _ = self.invoke(["run", str(ROOT / "configs/demo.toml"), "--baseline", str(filename), "--out", directory])
            self.assertEqual(code, 2)
            self.assertEqual(filename.read_bytes(), original)

    def test_output_failures_exit_two_without_raw_exception(self):
        with patch("accessproof.__main__.write_reports", side_effect=OSError("DO_NOT_PRINT_THIS")):
            code, _, error = self.invoke(["run", str(ROOT / "configs/demo.toml")], environment={})
        self.assertEqual(code, 2)
        self.assertNotIn("DO_NOT_PRINT_THIS", error)
