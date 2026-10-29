"""Pure assertion evaluation; uncertainty is never counted as a pass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .config import Assertion, Resource
from .transport import Observation

Status = Literal["passed", "failed", "inconclusive", "skipped"]
MISSING = object()


def lookup(body: object, pointer: str) -> object:
    current = body
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isascii() and part.isdigit() and (part == "0" or not part.startswith("0")):
            index = int(part)
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            return MISSING
    return current


def matches(observation: Observation, assertion: Assertion) -> bool:
    if observation.error or not observation.is_json or observation.status not in assertion.statuses:
        return False
    for pointer, expected in assertion.json_equals.items():
        actual = lookup(observation.body, pointer)
        # bool is a subclass of int in Python: True must not satisfy expected 1.
        if actual is MISSING or type(actual) is not type(expected) or actual != expected:
            return False
    return True


def assertion_evidence(observation: Observation, assertion: Assertion) -> list[dict]:
    checks = [{"kind": "status", "matched": observation.status in assertion.statuses}]
    for pointer, expected in assertion.json_equals.items():
        actual = lookup(observation.body, pointer)
        checks.append({"kind": "json_equals", "pointer": pointer,
                       "matched": actual is not MISSING and type(actual) is type(expected) and actual == expected})
    return checks


@dataclass
class Result:
    id: str
    kind: str
    identity: str
    resource: str | None
    expected: str
    status: Status
    reason: str
    required: bool = True
    evidence: dict = field(default_factory=dict)


def evaluate(observation: Observation, resource: Resource, expected: str, anonymous: bool) -> tuple[Status, str, dict]:
    evidence = observation.evidence()
    evidence["allow_assertions"] = assertion_evidence(observation, resource.allow)
    evidence["deny_assertions"] = assertion_evidence(observation, resource.deny)
    exposed = [pointer for pointer in resource.protected_paths if lookup(observation.body, pointer) is not MISSING]
    evidence["protected_fields_present"] = exposed
    # Even an error status can leak protected data. Only parsed, bounded bodies are examined.
    if expected == "deny" and exposed:
        return "failed", "protected_fields_exposed", evidence
    if observation.error:
        return "inconclusive", observation.error, evidence
    if observation.status is None or observation.status >= 500:
        return "inconclusive", "server_error", evidence
    if observation.status == 401 and not anonymous:
        return "inconclusive", "authentication_rejected", evidence
    allowed = matches(observation, resource.allow)
    denied = matches(observation, resource.deny)
    if allowed and denied:
        return "inconclusive", "ambiguous_assertions", evidence
    if expected == "allow":
        if allowed and len(exposed) == len(resource.protected_paths):
            return "passed", "expected_access_verified", evidence
        if denied and observation.status in {403, 404}:
            return "failed", "expected_access_denied", evidence
        return "inconclusive", "legitimate_response_not_verified", evidence
    if allowed:
        return "failed", "unexpected_access_verified", evidence
    if denied:
        return "passed", "expected_denial_verified", evidence
    return "inconclusive", "response_matches_neither_contract", evidence
