"""report.json is a public contract: the recorded gate verdict, the plain-language headline, and the schema."""

import copy
import json
import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from accessproof.reporting import compare, comparison_headline, sanitize, write_reports
from accessproof.runner import gate_failed, gate_verdict, run
from accessproof.transport import Observation
from tests.support import ENVIRONMENT, ROOT, TOKENS, FixtureTransport, observed, policy

try:
    from jsonschema import Draft202012Validator
except ImportError:  # Installed in CI from ci/requirements.txt; optional for local runs.
    Draft202012Validator = None

SCHEMA = json.loads((ROOT / "schema/report.schema.json").read_text(encoding="utf-8"))
SAMPLES = sorted(path for path in (ROOT / "docs/samples").glob("*.json") if path.name != "evaluation.json")


def fixture_report(override=None, configured=None, environment=ENVIRONMENT):
    return run(configured or policy(), environment=environment, transport=FixtureTransport(override))


def scenario_reports():
    """Reports covering every result kind, status, evidence shape, and comparison outcome."""
    clean = fixture_report()
    leak = fixture_report(
        lambda path, subject: (
            observed(200, {"id": "record-bob", "owner": "bob", "private_note": "x"})
            if path == "/records/record-bob" and subject == "alice"
            else None
        )
    )
    regression = copy.deepcopy(leak)
    compare(regression, clean)
    changed = fixture_report(configured=replace(policy(), policy_version="2"))
    compare(changed, clean)
    trimmed = copy.deepcopy(clean)
    trimmed["results"].pop()
    coverage = copy.deepcopy(clean)
    compare(coverage, trimmed)
    configured = policy()
    resource = next(item for item in configured.resources if item.id == "bob-record")
    permissions = {key: value for key, value in resource.permissions.items() if key != "alice"}
    skipped = replace(resource, permissions=permissions, skip={"alice": "fixture temporarily unavailable"})
    skip_report = fixture_report(
        configured=replace(
            configured, resources=tuple(skipped if item.id == "bob-record" else item for item in configured.resources)
        )
    )
    missing = dict(ENVIRONMENT)
    missing.pop("ACCESSPROOF_BOB_TOKEN")
    return {
        "clean": clean,
        "leak": leak,
        "regression": regression,
        "policy_changed": changed,
        "coverage_mismatch": coverage,
        "skipped": skip_report,
        "missing_credential": fixture_report(environment=missing),
        "network_errors": fixture_report(lambda path, subject: Observation(error="network_timeout")),
    }


class GateVerdictTests(unittest.TestCase):
    def test_every_report_records_a_gate_that_matches_the_decision(self):
        for name, report in scenario_reports().items():
            with self.subTest(scenario=name):
                self.assertEqual(report["gate"], gate_verdict(report))
                self.assertEqual(report["gate"]["status"] == "blocked", gate_failed(report))

    def test_gate_explains_why_it_blocked(self):
        reports = scenario_reports()
        self.assertEqual(reports["clean"]["gate"], {"status": "passed", "reasons": [], "blocking_checks": []})
        self.assertEqual(reports["regression"]["gate"]["reasons"], ["required_checks_not_passed"])
        self.assertEqual(reports["regression"]["gate"]["blocking_checks"], ["permission:bob-record:alice"])
        self.assertEqual(reports["policy_changed"]["gate"]["reasons"], ["comparison_policy_changed"])
        self.assertEqual(reports["policy_changed"]["gate"]["blocking_checks"], [])
        self.assertEqual(reports["coverage_mismatch"]["gate"]["reasons"], ["comparison_coverage_mismatch"])

    def test_compare_refreshes_a_stale_gate(self):
        clean = fixture_report()
        changed = fixture_report(configured=replace(policy(), policy_version="2"))
        self.assertEqual(changed["gate"]["status"], "passed")
        compare(changed, clean)
        self.assertEqual(changed["gate"]["status"], "blocked")


class ComparisonHeadlineTests(unittest.TestCase):
    def test_headline_states_the_outcome_in_plain_language(self):
        reports = scenario_reports()
        self.assertEqual(comparison_headline(reports["clean"]["comparison"]), "No baseline comparison requested")
        self.assertEqual(
            comparison_headline(reports["regression"]["comparison"]), "Compared with baseline: 1 newly failing"
        )
        self.assertIn("policy changed", comparison_headline(reports["policy_changed"]["comparison"]))
        self.assertIn("set of checks differs", comparison_headline(reports["coverage_mismatch"]["comparison"]))
        unchanged = fixture_report()
        compare(unchanged, fixture_report())
        self.assertEqual(comparison_headline(unchanged["comparison"]), "Compared with baseline: no changes")


@unittest.skipIf(Draft202012Validator is None, "jsonschema is not installed (pip install -r ci/requirements.txt)")
class ReportSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Draft202012Validator.check_schema(SCHEMA)
        cls.validator = Draft202012Validator(SCHEMA, format_checker=Draft202012Validator.FORMAT_CHECKER)

    def assertValid(self, report):
        errors = [f"{list(error.absolute_path)}: {error.message}" for error in self.validator.iter_errors(report)]
        self.assertEqual(errors, [])

    def test_generated_reports_conform(self):
        for name, report in scenario_reports().items():
            with self.subTest(scenario=name):
                self.assertValid(sanitize(report, list(TOKENS.values())))

    def test_written_report_file_conforms(self):
        with tempfile.TemporaryDirectory() as directory:
            write_reports(sanitize(fixture_report(), list(TOKENS.values())), directory)
            self.assertValid(json.loads((Path(directory) / "report.json").read_text(encoding="utf-8")))

    def test_published_samples_conform_and_record_the_gate(self):
        self.assertEqual(len(SAMPLES), 3)
        for path in SAMPLES:
            with self.subTest(sample=path.name):
                sample = json.loads(path.read_text(encoding="utf-8"))
                self.assertValid(sample)
                self.assertIn("gate", sample)

    def test_schema_acts_as_a_disclosure_allowlist(self):
        report = sanitize(fixture_report(), [])
        for mutation in (
            lambda r: r.update(response_body="{}"),
            lambda r: r["results"][0]["evidence"].update(headers={"set-cookie": "x"}),
            lambda r: r["results"][0]["evidence"].update(body="private"),
            lambda r: r["results"][0].update(token="secret"),
            lambda r: r["gate"].update(status="unknown"),
        ):
            with self.subTest(mutation=mutation):
                mutated = copy.deepcopy(report)
                mutation(mutated)
                self.assertTrue(list(self.validator.iter_errors(mutated)))

    def test_reports_written_before_the_gate_field_still_conform(self):
        legacy = sanitize(fixture_report(), [])
        del legacy["gate"]
        self.assertValid(legacy)


class ReasonCodeDocumentationTests(unittest.TestCase):
    def test_every_reason_a_report_can_contain_is_documented(self):
        documented = set(re.findall(r"^\| `([a-z_]+)` \|", (ROOT / "docs/report-format.md").read_text(), re.M))
        emitted = {result["reason"] for report in scenario_reports().values() for result in report["results"]}
        emitted |= {reason for report in scenario_reports().values() for reason in report["gate"]["reasons"]}
        transport_errors = set(re.findall(r'error="([a-z_]+)"', (ROOT / "accessproof/transport.py").read_text()))
        self.assertTrue(transport_errors)
        self.assertEqual((emitted | transport_errors) - documented, set())
