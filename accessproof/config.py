"""Strict TOML policy validation. Credentials are references, never config values."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

from . import EVALUATOR_VERSION


class ConfigError(ValueError):
    """An actionable validation error containing no input values."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def table(value: object, allowed: set[str], required: set[str], where: str) -> dict:
    require(isinstance(value, dict), f"{where}: expected a table")
    require(not set(value) - allowed, f"{where}: unknown keys (check spelling; credentials belong in environment variables)")
    require(not required - set(value), f"{where}: missing required keys")
    return value


def string(value: object, where: str) -> str:
    require(isinstance(value, str) and bool(value) and len(value) <= 256,
            f"{where}: expected a nonempty string of at most 256 characters")
    require(all(ord(char) >= 32 and ord(char) != 127 for char in value),
            f"{where}: control characters are forbidden")
    return value


def identifier(value: object) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", value) is not None,
            "IDs must start with a letter and contain only letters, digits, hyphens, or underscores (max 64)")
    return value


def path(value: object) -> str:
    value = string(value, "endpoint path")
    require(re.fullmatch(r"/[A-Za-z0-9_./~-]*", value) is not None,
            "endpoint path: use a literal absolute path without query, fragment, encoding, or credentials")
    require("//" not in value and not {".", ".."}.intersection(value.split("/")),
            "endpoint path: repeated slashes and dot segments are forbidden")
    return value


def pointer(value: object) -> str:
    value = string(value, "JSON pointer")
    require(value.startswith("/") and re.search(r"~(?![01])", value) is None,
            "JSON pointers must start with / and use ~0 or ~1 escapes")
    return value


@dataclass(frozen=True)
class Assertion:
    statuses: tuple[int, ...]
    json_equals: dict[str, object]


def assertion(raw: object, *, success: bool = False) -> Assertion:
    raw = table(raw, {"statuses", "json_equals"}, {"statuses", "json_equals"}, "assertion")
    statuses = raw["statuses"]
    permitted = set(range(200, 300)) if success else {200, 401, 403, 404}
    require(isinstance(statuses, list) and bool(statuses)
            and all(type(code) is int and code in permitted for code in statuses),
            "assertion: allow/verify statuses must be 2xx; deny statuses must be 200, 401, 403, or 404")
    require(len(statuses) == len(set(statuses)), "assertion: duplicate statuses")
    equals = raw["json_equals"]
    require(isinstance(equals, dict) and bool(equals), "assertion: at least one JSON content assertion is required")
    for key, value in equals.items():
        pointer(key)
        require(type(value) in (str, int, bool), "assertion: expected values must be strings, integers, or booleans")
        if isinstance(value, str):
            string(value, "assertion value")
    return Assertion(tuple(sorted(statuses)), equals)


@dataclass(frozen=True)
class Target:
    base_url: str
    environment: str
    timeout_seconds: int = 3
    max_response_bytes: int = 65536

    @property
    def address(self) -> tuple[str, int, str]:
        parsed = urlsplit(self.base_url)
        return parsed.hostname, parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80), parsed.scheme


def target(raw: object) -> Target:
    raw = table(raw, {"base_url", "environment", "timeout_seconds", "max_response_bytes"},
                {"base_url", "environment"}, "target")
    url = string(raw["base_url"], "target.base_url")
    try:
        parsed = urlsplit(url)
        require(parsed.scheme in {"http", "https"} and parsed.hostname is not None,
                "target.base_url: HTTP or HTTPS with a literal loopback IP is required")
        host = ipaddress.ip_address(parsed.hostname)
        require(host.is_loopback, "target.base_url: v1 permits only literal loopback IP addresses")
        require(parsed.username is None and parsed.password is None and parsed.path in ("", "/")
                and not parsed.query and not parsed.fragment and "%" not in url and "?" not in url and "#" not in url,
                "target.base_url: userinfo, paths, query strings, and fragments are forbidden")
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        require(1 <= port <= 65535, "target.base_url: invalid port")
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError("target.base_url: invalid URL or IP; use a literal loopback IP") from None
    require(raw["environment"] in ("development", "test"), "target.environment: must be development or test")
    timeout = raw.get("timeout_seconds", 3)
    size = raw.get("max_response_bytes", 65536)
    require(type(timeout) is int and 1 <= timeout <= 30, "target.timeout_seconds: expected integer 1–30")
    require(type(size) is int and 1024 <= size <= 1048576, "target.max_response_bytes: expected integer 1024–1048576")
    # Normalize harmless spelling differences before fingerprinting.
    hostname = f"[{host}]" if host.version == 6 else str(host)
    return Target(f"{parsed.scheme}://{hostname}:{port}", raw["environment"], timeout, size)


@dataclass(frozen=True)
class Identity:
    id: str
    token_env: str | None
    verify_path: str | None
    verify: Assertion | None
    subject_pointer: str | None = None

    @property
    def anonymous(self) -> bool:
        return self.token_env is None


@dataclass(frozen=True)
class Resource:
    id: str
    path: str
    owner: str
    positive_identity: str
    allow: Assertion
    deny: Assertion
    protected_paths: tuple[str, ...]
    permissions: dict[str, str]
    skip: dict[str, str]
    required: bool = True


@dataclass(frozen=True)
class Policy:
    schema_version: int
    suite_id: str
    policy_version: str
    target: Target
    identities: tuple[Identity, ...]
    resources: tuple[Resource, ...]

    @property
    def fingerprint(self) -> str:
        canonical = {"evaluator_version": EVALUATOR_VERSION, "policy": asdict(self)}
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_policy(filename: str | Path) -> Policy:
    try:
        require(Path(filename).stat().st_size <= 262144, "configuration exceeds 256 KiB")
        with open(filename, "rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError, UnicodeError):
        raise ConfigError("cannot read configuration: check the file path and TOML syntax") from None
    return parse_policy(raw)


def parse_policy(raw: object) -> Policy:
    raw = table(raw, {"schema_version", "suite_id", "policy_version", "target", "identities", "resources"},
                {"schema_version", "suite_id", "policy_version", "target", "identities", "resources"}, "configuration")
    require(type(raw["schema_version"]) is int and raw["schema_version"] == 1, "unsupported schema_version; expected 1")
    suite = identifier(raw["suite_id"])
    version = string(raw["policy_version"], "policy_version")
    configured_target = target(raw["target"])
    identity_raw = raw["identities"]
    require(isinstance(identity_raw, dict) and 2 <= len(identity_raw) <= 16, "identities: expected 2–16 named identity tables")
    identities = []
    for name, entry in sorted(identity_raw.items()):
        identifier(name)
        entry = table(entry, {"anonymous", "token_env", "verify_path", "verify", "subject_pointer"}, set(), "identity")
        require(type(entry.get("anonymous", False)) is bool, "identity.anonymous: expected a boolean")
        if entry.get("anonymous", False):
            require(set(entry) == {"anonymous"}, "anonymous identity must not contain authentication settings")
            identities.append(Identity(name, None, None, None))
            continue
        require({"token_env", "verify_path", "verify"} <= set(entry), "identity: token_env, verify_path, and verify are required")
        env_name = string(entry["token_env"], "token_env")
        require(re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", env_name) is not None, "token_env: expected an uppercase environment variable name")
        subject_pointer = pointer(entry.get("subject_pointer", "/subject"))
        verify = assertion(entry["verify"], success=True)
        require(isinstance(verify.json_equals.get(subject_pointer), str),
                "identity.verify: assert the expected subject at subject_pointer (default /subject)")
        identities.append(Identity(name, env_name, path(entry["verify_path"]), verify, subject_pointer))
    require(sum(identity.anonymous for identity in identities) == 1, "configure exactly one anonymous identity")
    env_names = [identity.token_env for identity in identities if not identity.anonymous]
    require(len(set(env_names)) == len(env_names), "authenticated identities must use different token environment variables")
    subjects = [identity.verify.json_equals[identity.subject_pointer] for identity in identities if not identity.anonymous]
    require(len(set(subjects)) == len(subjects), "authenticated identities must assert distinct subjects")
    names = {identity.id for identity in identities}
    authenticated = {identity.id for identity in identities if not identity.anonymous}
    resources_raw = raw["resources"]
    require(isinstance(resources_raw, list) and 1 <= len(resources_raw) <= 100, "resources: expected 1–100 resource tables")
    resources = []
    for entry in resources_raw:
        entry = table(entry, {"id", "path", "owner", "positive_identity", "allow", "deny", "protected_paths", "permissions", "skip", "required"},
                      {"id", "path", "owner", "positive_identity", "allow", "deny", "protected_paths", "permissions"}, "resource")
        resource_id = identifier(entry["id"])
        owner = identifier(entry["owner"])
        positive = identifier(entry["positive_identity"])
        require(owner in authenticated and positive in authenticated, "resource: owner and positive_identity must reference authenticated identities")
        permissions = entry["permissions"]
        skipped = entry.get("skip", {})
        require(isinstance(permissions, dict) and set(permissions) <= names
                and all(value in ("allow", "deny") for value in permissions.values()), "resource.permissions: unknown identity or permission")
        require(isinstance(skipped, dict) and set(skipped) <= names, "resource.skip: unknown identity")
        require(not set(permissions).intersection(skipped), "resource: an identity cannot have both a permission and a skip")
        for reason in skipped.values():
            string(reason, "skip reason")
        require(permissions.get(owner) == "allow" and permissions.get(positive) == "allow", "resource: owner and positive_identity must have allow permission")
        paths = entry["protected_paths"]
        require(isinstance(paths, list) and bool(paths), "resource.protected_paths: expected at least one JSON pointer")
        for item in paths:
            pointer(item)
        require(len(paths) == len(set(paths)), "resource.protected_paths: duplicate pointer")
        required = entry.get("required", True)
        require(type(required) is bool, "resource.required: expected a boolean")
        resources.append(Resource(resource_id, path(entry["path"]), owner, positive,
                                  assertion(entry["allow"], success=True), assertion(entry["deny"]),
                                  tuple(sorted(paths)), permissions, skipped, required))
    require(len({resource.id for resource in resources}) == len(resources), "resource IDs must be unique")
    return Policy(1, suite, version, configured_target, tuple(identities), tuple(sorted(resources, key=lambda resource: resource.id)))
