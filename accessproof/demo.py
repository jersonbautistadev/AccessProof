"""Synthetic local-only application with an intentionally broken authorization mode."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os

from .config import require

TOKEN_VARIABLES = {"alice": "ACCESSPROOF_ALICE_TOKEN", "bob": "ACCESSPROOF_BOB_TOKEN", "admin": "ACCESSPROOF_ADMIN_TOKEN"}
RECORDS = {
    "record-alice": {"id": "record-alice", "owner": "alice", "private_note": "SYNTHETIC_ALICE_PRIVATE_NOTE"},
    "record-bob": {"id": "record-bob", "owner": "bob", "private_note": "SYNTHETIC_BOB_PRIVATE_NOTE"},
}
AUDIT = {"id": "audit", "entries": [{"event": "synthetic-login", "subject": "alice"}]}


def make_server(*, port: int = 8765, mode: str = "fixed", tokens: dict[str, str]) -> ThreadingHTTPServer:
    require(mode in {"fixed", "vulnerable"}, "demo: mode must be fixed or vulnerable")
    require(type(port) is int and 0 <= port <= 65535, "demo: invalid port")
    require(set(tokens) == set(TOKEN_VARIABLES), "demo: provide all three synthetic identities")
    require(all(isinstance(token, str) and 16 <= len(token) <= 4096
                and all(33 <= ord(char) <= 126 for char in token) for token in tokens.values()),
            "demo: set all three token environment variables to distinct ASCII strings of 16–4096 characters")
    require(len(set(tokens.values())) == 3, "demo: tokens must be distinct")

    class Handler(BaseHTTPRequestHandler):
        server_version = "AccessProofDemo/0.1"

        def log_message(self, *_):
            # Default HTTP logs may retain attacker-controlled paths. No request logs in the demo.
            pass

        def respond(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/health":
                self.respond(200, {"status": "ready"})
                return
            authorization = self.headers.get("Authorization", "")
            subject = None
            for candidate, token in tokens.items():
                if hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
                    subject = candidate
                    break
            if subject is None:
                self.respond(401, {"error": "access_denied"})
                return
            role = "admin" if subject == "admin" else "user"
            if self.path == "/me":
                self.respond(200, {"subject": subject, "role": role})
                return
            if self.path.startswith("/records/"):
                record = RECORDS.get(self.path.removeprefix("/records/"))
                if record is None:
                    self.respond(404, {"error": "not_found"})
                    return
                # The intentional BOLA bug: vulnerable mode omits the ownership check.
                if mode == "fixed" and role != "admin" and record["owner"] != subject:
                    self.respond(403, {"error": "access_denied"})
                    return
                self.respond(200, record)
                return
            if self.path == "/admin/audit":
                # The intentional function authorization bug: vulnerable mode omits the role check.
                if mode == "fixed" and role != "admin":
                    self.respond(403, {"error": "access_denied"})
                    return
                self.respond(200, AUDIT)
                return
            self.respond(404, {"error": "not_found"})

    # Binding is intentionally hard-coded. There is no public-bind flag.
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve(port: int, mode: str) -> None:
    tokens = {name: os.environ.get(variable, "") for name, variable in TOKEN_VARIABLES.items()}
    server = make_server(port=port, mode=mode, tokens=tokens)
    print(f"Synthetic demo: {mode} | http://127.0.0.1:{server.server_port} | Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
