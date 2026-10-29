"""Verify identities, establish positive controls, then check the permission matrix."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import os

from . import EVALUATOR_VERSION, __version__
from .config import Policy
from .evaluation import Result, assertion_evidence, evaluate, matches
from .transport import GetTransport


def credentials(policy: Policy, environment: dict[str, str]) -> tuple[dict, dict]:
    tokens, errors = {}, {}
    for identity in policy.identities:
        if identity.anonymous:
            tokens[identity.id] = None
            continue
        token = environment.get(identity.token_env, "")
        if not token:
            errors[identity.id] = "credential_missing"
        elif not (16 <= len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token)):
            errors[identity.id] = "credential_invalid"
        else:
            tokens[identity.id] = token
    # Different environment variable names can still point to the same account token.
    counts = Counter(token for token in tokens.values() if token is not None)
    for identity_id, token in tokens.items():
        if token is not None and counts[token] > 1:
            errors[identity_id] = "credential_reused_across_identities"
    return tokens, errors


def run(policy: Policy, *, environment: dict[str, str] | None = None, transport=None) -> dict:
    environment = dict(os.environ) if environment is None else environment
    transport = GetTransport(policy.target) if transport is None else transport
    tokens, credential_errors = credentials(policy, environment)
    results = []
    identity_ready = {}
    for identity in policy.identities:
        if identity.anonymous:
            identity_ready[identity.id] = True
            continue
        reason = credential_errors.get(identity.id)
        evidence = {}
        if reason is None:
            observation = transport.get(identity.verify_path, tokens[identity.id])
            evidence = observation.evidence()
            evidence["identity_assertions"] = assertion_evidence(observation, identity.verify)
            passed = matches(observation, identity.verify)
            reason = "identity_verified" if passed else observation.error or "identity_not_verified"
        else:
            passed = False
        identity_ready[identity.id] = passed
        results.append(Result(f"identity:{identity.id}", "identity", identity.id, None, "verified identity",
                              "passed" if passed else "inconclusive", reason, evidence=evidence))

    controls = {}
    for resource in policy.resources:
        actor = resource.positive_identity
        observation = None
        evidence = {}
        if not identity_ready[actor]:
            status, reason = "inconclusive", "control_identity_not_verified"
        else:
            observation = transport.get(resource.path, tokens[actor])
            status, reason, evidence = evaluate(observation, resource, "allow", False)
            if status != "passed":
                evidence["control_diagnostic"] = reason
                status, reason = "inconclusive", "positive_control_not_verified"
        control = Result(f"control:{resource.id}", "control", actor, resource.id, "known legitimate access",
                         status, reason, resource.required, evidence)
        results.append(control)
        controls[resource.id] = (control, observation)

    for resource in policy.resources:
        control, positive_observation = controls[resource.id]
        for identity in policy.identities:
            expected = resource.permissions.get(identity.id, "unspecified")
            evidence = {}
            if identity.id in resource.skip:
                status, reason = "skipped", "explicit_skip"
                evidence = {"skip_reason": resource.skip[identity.id]}
            elif expected == "unspecified":
                status, reason = "skipped", "permission_not_configured"
            elif not identity_ready[identity.id]:
                status, reason = "inconclusive", "identity_not_verified"
            elif control.status != "passed":
                status, reason = "inconclusive", "positive_control_not_verified"
            else:
                # Reuse this actor's just-verified positive response; no artificial duplicate request.
                observation = positive_observation if identity.id == resource.positive_identity else transport.get(resource.path, tokens[identity.id])
                status, reason, evidence = evaluate(observation, resource, expected, identity.anonymous)
            results.append(Result(f"permission:{resource.id}:{identity.id}", "permission", identity.id,
                                  resource.id, expected, status, reason, resource.required, evidence))

    report = {
        "report_version": 1,
        "tool_version": __version__,
        "evaluator_version": EVALUATOR_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite_id": policy.suite_id,
        "policy_version": policy.policy_version,
        "policy_fingerprint": policy.fingerprint,
        "target": policy.target.base_url,
        "scope": {"method": "GET", "configured_resources": len(policy.resources),
                  "configured_identities": len(policy.identities), "permission_checks": len(policy.resources) * len(policy.identities)},
        "summary": dict(Counter(result.status for result in results)),
        "results": [asdict(result) for result in results],
        "comparison": {"status": "not_requested", "newly_failing": [], "newly_inconclusive": [], "resolved": [], "added": [], "removed": []},
        "limitation": "Passing configured checks does not establish that an entire application is secure.",
    }
    return report


def gate_failed(report: dict) -> bool:
    if report["comparison"]["status"] not in {"not_requested", "equivalent"}:
        return True
    # Required skipped checks also block: an omitted test is not evidence of a pass.
    return any(result["required"] and result["status"] != "passed" for result in report["results"])
