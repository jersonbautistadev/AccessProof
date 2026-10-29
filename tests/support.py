from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import threading

from accessproof.config import load_policy
from accessproof.demo import AUDIT, RECORDS, TOKEN_VARIABLES, make_server
from accessproof.transport import Observation

ROOT = Path(__file__).resolve().parents[1]
TOKENS = {"alice": "demo-alice-token-0001", "bob": "demo-bob-token-000002", "admin": "demo-admin-token-0003"}
ENVIRONMENT = {TOKEN_VARIABLES[name]: token for name, token in TOKENS.items()}


def policy():
    return load_policy(ROOT / "configs/demo.toml")


def observed(status, body):
    return Observation(status, body, body_bytes=123, is_json=True)


@contextmanager
def running_demo(mode="fixed"):
    server = make_server(port=0, mode=mode, tokens=TOKENS)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    configured = policy()
    configured = replace(configured, target=replace(configured.target, base_url=f"http://127.0.0.1:{server.server_port}"))
    try:
        yield configured
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class FixtureTransport:
    """Fixed application oracle plus explicitly injected faults; no evaluation logic."""
    def __init__(self, override=None):
        self.override = override
        self.calls = []

    def get(self, path, token):
        subject = next((name for name, value in TOKENS.items() if value == token), None)
        self.calls.append((path, subject))
        if self.override:
            replacement = self.override(path, subject)
            if replacement is not None:
                return replacement
        if subject is None:
            return observed(401, {"error": "access_denied"})
        if path == "/me":
            return observed(200, {"subject": subject, "role": "admin" if subject == "admin" else "user"})
        if path == "/admin/audit":
            return observed(200, AUDIT) if subject == "admin" else observed(403, {"error": "access_denied"})
        record = RECORDS.get(path.removeprefix("/records/"))
        if record is None:
            return observed(404, {"error": "not_found"})
        return observed(200, record) if subject in (record["owner"], "admin") else observed(403, {"error": "access_denied"})
