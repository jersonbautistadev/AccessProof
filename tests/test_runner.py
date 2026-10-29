from dataclasses import replace
import json
import unittest

from accessproof.config import Assertion
from accessproof.evaluation import MISSING, lookup, matches
from accessproof.runner import gate_failed, run
from accessproof.transport import Observation
from tests.support import ENVIRONMENT, FixtureTransport, TOKENS, observed, policy, running_demo


class RunnerTests(unittest.TestCase):
    def result(self, report, check_id):
        return next(result for result in report["results"] if result["id"] == check_id)

    def run_fixture(self, override=None, configured=None, environment=None):
        return run(configured or policy(), environment=ENVIRONMENT if environment is None else environment,
                   transport=FixtureTransport(override))

    def test_real_vulnerable_demo_detects_exact_four_known_bugs(self):
        with running_demo("vulnerable") as configured:
            report = run(configured, environment=ENVIRONMENT)
        failures = {row["id"] for row in report["results"] if row["status"] == "failed"}
        self.assertEqual(failures, {"permission:alice-record:bob", "permission:bob-record:alice",
                                    "permission:admin-audit:alice", "permission:admin-audit:bob"})
        self.assertEqual(report["summary"], {"passed": 14, "failed": 4})
        self.assertTrue(gate_failed(report))

    def test_real_fixed_demo_has_no_false_positives_in_configured_matrix(self):
        with running_demo() as configured:
            report = run(configured, environment=ENVIRONMENT)
        self.assertEqual(report["summary"], {"passed": 18})
        self.assertFalse(gate_failed(report))

    def test_controls_run_before_permission_checks(self):
        transport = FixtureTransport()
        report = run(policy(), environment=ENVIRONMENT, transport=transport)
        self.assertFalse(gate_failed(report))
        self.assertEqual([path for path, _ in transport.calls[:3]], ["/me"] * 3)
        self.assertEqual(transport.calls[3:6], [("/admin/audit", "admin"), ("/records/record-alice", "alice"), ("/records/record-bob", "bob")])
        self.assertEqual(len(transport.calls), 15)  # Three positive observations are reused.

    def test_missing_reused_invalid_credentials_remain_visible(self):
        for value, expected in ((None, "credential_missing"), (TOKENS["bob"], "credential_reused_across_identities"),
                                ("too-short", "credential_invalid"), ("x" * 20 + "\r\n", "credential_invalid")):
            with self.subTest(value=value):
                environment = dict(ENVIRONMENT)
                if value is None:
                    environment.pop("ACCESSPROOF_ALICE_TOKEN")
                else:
                    environment["ACCESSPROOF_ALICE_TOKEN"] = value
                report = self.run_fixture(environment=environment)
                identity = self.result(report, "identity:alice")
                self.assertEqual((identity["status"], identity["reason"]), ("inconclusive", expected))
                self.assertEqual(self.result(report, "permission:bob-record:alice")["status"], "inconclusive")
                self.assertTrue(gate_failed(report))

    def test_wrong_subject_or_role_cannot_pass_identity_verification(self):
        for body in ({"subject": "bob", "role": "user"}, {"subject": "alice", "role": "admin"}):
            report = self.run_fixture(lambda path, subject: observed(200, body) if path == "/me" and subject == "alice" else None)
            self.assertEqual(self.result(report, "identity:alice")["status"], "inconclusive")

    def test_an_all_denied_application_is_not_a_clean_run(self):
        report = self.run_fixture(lambda path, subject: observed(403, {"error": "access_denied"}) if path != "/me" else None)
        permissions = [result for result in report["results"] if result["kind"] == "permission"]
        self.assertEqual(len(permissions), 12)
        self.assertTrue(all(result["status"] == "inconclusive" for result in permissions))
        self.assertTrue(gate_failed(report))

    def test_missing_resource_blocks_its_entire_matrix(self):
        report = self.run_fixture(lambda path, subject: observed(404, {"error": "not_found"}) if path == "/records/record-alice" else None)
        rows = [row for row in report["results"] if row["resource"] == "alice-record"]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["status"] == "inconclusive" for row in rows))

    def test_authenticated_401_after_valid_preflight_is_inconclusive(self):
        report = self.run_fixture(lambda path, subject: observed(401, {"error": "access_denied"}) if path == "/admin/audit" and subject == "alice" else None)
        row = self.result(report, "permission:admin-audit:alice")
        self.assertEqual((row["status"], row["reason"]), ("inconclusive", "authentication_rejected"))

    def test_403_with_private_fields_fails(self):
        report = self.run_fixture(lambda path, subject: observed(403, {"error": "access_denied", "private_note": "NEVER_REPORT_THIS"})
                                  if path == "/records/record-bob" and subject == "alice" else None)
        row = self.result(report, "permission:bob-record:alice")
        self.assertEqual((row["status"], row["reason"]), ("failed", "protected_fields_exposed"))
        self.assertNotIn("NEVER_REPORT_THIS", json.dumps(report))

    def test_200_is_not_automatically_access(self):
        for body in ({"message": "please log in"}, {"id": "wrong-record"}, {"error": "access_denied"}):
            report = self.run_fixture(lambda path, subject: observed(200, body) if path == "/records/record-bob" and subject == "alice" else None)
            self.assertEqual(self.result(report, "permission:bob-record:alice")["status"], "inconclusive")

    def test_200_denial_can_be_explicitly_configured(self):
        configured = policy()
        resources = tuple(replace(resource, deny=Assertion((200, 401, 403), {"/error": "access_denied"})) for resource in configured.resources)
        report = self.run_fixture(lambda path, subject: observed(200, {"error": "access_denied"}) if path == "/records/record-bob" and subject == "alice" else None,
                                  configured=replace(configured, resources=resources))
        self.assertEqual(self.result(report, "permission:bob-record:alice")["status"], "passed")

    def test_expected_allow_denied_is_failed_when_other_positive_control_works(self):
        report = self.run_fixture(lambda path, subject: observed(403, {"error": "access_denied"}) if path == "/records/record-bob" and subject == "admin" else None)
        self.assertEqual(self.result(report, "permission:bob-record:admin")["status"], "failed")

    def test_network_errors_never_pass(self):
        report = self.run_fixture(lambda path, subject: Observation(error="network_error"))
        self.assertEqual(report["summary"], {"inconclusive": 18})

    def test_unknown_denial_server_errors_and_nonjson_are_inconclusive(self):
        for observation in (observed(403, {"error": "unexpected"}), observed(500, {"error": "access_denied"}),
                            Observation(status=200, error="non_json_response"), Observation(error="network_timeout")):
            report = self.run_fixture(lambda path, subject: observation if path == "/admin/audit" and subject == "alice" else None)
            self.assertEqual(self.result(report, "permission:admin-audit:alice")["status"], "inconclusive")

    def test_unconfigured_and_explicitly_skipped_checks_block_required_scope(self):
        configured = policy()
        resource = next(item for item in configured.resources if item.id == "bob-record")
        permissions = {key: value for key, value in resource.permissions.items() if key != "alice"}
        for skipped in ({}, {"alice": "fixture temporarily unavailable"}):
            changed = replace(resource, permissions=permissions, skip=skipped)
            new_policy = replace(configured, resources=tuple(changed if item.id == resource.id else item for item in configured.resources))
            report = self.run_fixture(configured=new_policy)
            self.assertEqual(self.result(report, "permission:bob-record:alice")["status"], "skipped")
            self.assertTrue(gate_failed(report))
            optional = replace(changed, required=False)
            optional_policy = replace(new_policy, resources=tuple(optional if item.id == resource.id else item for item in new_policy.resources))
            self.assertFalse(gate_failed(self.run_fixture(configured=optional_policy)))

    def test_json_pointer_escaping_arrays_and_type_strictness(self):
        self.assertEqual(lookup({"a/b": {"~key": ["first"]}}, "/a~1b/~0key/0"), "first")
        self.assertIs(lookup({"list": ["first"]}, "/list/01"), MISSING)
        self.assertIs(lookup({"list": []}, "/list/0"), MISSING)
        self.assertFalse(matches(observed(200, {"value": True}), Assertion((200,), {"/value": 1})))

    def test_documents_deliberately_missed_unconfigured_field_leak(self):
        # A real limitation: the configured private_note marker does not cover another field.
        report = self.run_fixture(lambda path, subject: observed(403, {"error": "access_denied", "unconfigured_private_field": "MISSED_LEAK"})
                                  if path == "/records/record-bob" and subject == "alice" else None)
        self.assertEqual(self.result(report, "permission:bob-record:alice")["status"], "passed")
        self.assertNotIn("MISSED_LEAK", json.dumps(report))

    def test_wrong_policy_can_flag_legitimate_application_behavior(self):
        configured = policy()
        resources = tuple(replace(resource, permissions={**resource.permissions, "alice": "allow"})
                          if resource.id == "admin-audit" else resource for resource in configured.resources)
        report = self.run_fixture(configured=replace(configured, resources=resources))
        row = self.result(report, "permission:admin-audit:alice")
        self.assertEqual((row["status"], row["reason"]), ("failed", "expected_access_denied"))
