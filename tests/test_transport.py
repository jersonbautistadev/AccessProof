import threading
import time
import unittest
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from accessproof.config import ConfigError
from accessproof.transport import GetTransport
from tests.support import policy


@contextmanager
def response_server():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            calls.append({"path": self.path, "cookie": self.headers.get("Cookie")})
            content_type = "application/json"
            encoding = None
            status = 200
            payload = b'{"ok":true}'
            if self.path == "/redirect":
                status = 302
            elif self.path == "/huge":
                payload = b"x" * 2048
            elif self.path == "/duplicate":
                payload = b'{"ok":true,"ok":false}'
            elif self.path == "/invalid":
                payload = b"not-json"
            elif self.path == "/array":
                payload = b"[]"
            elif self.path == "/nonstandard":
                payload = b'{"ok":NaN}'
            elif self.path == "/html":
                content_type = "text/html"
                payload = b"<h1>Login</h1>"
            elif self.path == "/gzip":
                encoding = "gzip"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            declared = 64 if self.path == "/trickle" else len(payload) + (10 if self.path == "/truncated" else 0)
            self.send_header("Content-Length", str(declared))
            self.send_header("Set-Cookie", "session=DO_NOT_REUSE")
            if status == 302:
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/redirect-target")
            if encoding:
                self.send_header("Content-Encoding", encoding)
            if self.path == "/trickle":
                # Each byte arrives well inside the 1 s socket timeout, but the whole body takes ~2 s.
                self.end_headers()
                try:
                    for _ in range(8):
                        self.wfile.write(b" ")
                        time.sleep(0.25)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return
            self.end_headers()
            if self.path == "/timeout":
                time.sleep(1.1)
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    configured = replace(
        policy().target, base_url=f"http://127.0.0.1:{server.server_port}", timeout_seconds=1, max_response_bytes=1024
    )
    try:
        yield GetTransport(configured), calls, server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class TransportTests(unittest.TestCase):
    def test_real_http_transport_does_not_follow_redirects_or_reuse_cookies(self):
        with response_server() as (transport, calls, _):
            self.assertEqual(transport.get("/redirect", "synthetic-token-0001").error, "redirect_refused")
            self.assertEqual([call["path"] for call in calls], ["/redirect"])
            self.assertIsNone(transport.get("/ok", None).error)
            self.assertTrue(all(call["cookie"] is None for call in calls))

    def test_proxy_environment_is_not_used(self):
        with (
            response_server() as (transport, _, _),
            patch.dict(
                "os.environ",
                {
                    "HTTP_PROXY": "http://127.0.0.1:1",
                    "HTTPS_PROXY": "http://127.0.0.1:1",
                    "ALL_PROXY": "http://127.0.0.1:1",
                    "NO_PROXY": "",
                },
            ),
        ):
            self.assertEqual(transport.get("/ok", None).body, {"ok": True})

    def test_response_limits_and_unsupported_content_fail_inconclusively(self):
        with response_server() as (transport, _, _):
            for endpoint, expected in (
                ("/huge", "response_too_large"),
                ("/duplicate", "invalid_json"),
                ("/invalid", "invalid_json"),
                ("/nonstandard", "invalid_json"),
                ("/array", "json_object_required"),
                ("/html", "non_json_response"),
                ("/gzip", "encoded_response_unsupported"),
                ("/truncated", "truncated_response"),
            ):
                with self.subTest(endpoint=endpoint):
                    self.assertEqual(transport.get(endpoint, None).error, expected)

    def test_read_timeout_is_visible(self):
        with response_server() as (transport, _, _):
            self.assertEqual(transport.get("/timeout", None).error, "network_timeout")

    def test_connection_errors_do_not_leak_exceptions(self):
        with patch("http.client.HTTPConnection.request", side_effect=OSError("sensitive-connection-details")):
            observation = GetTransport(policy().target).get("/me", None)
        self.assertEqual(observation.error, "network_error")
        self.assertNotIn("sensitive-connection-details", str(observation))

    def test_transport_revalidates_target_and_endpoint(self):
        with self.assertRaises(ConfigError):
            GetTransport(replace(policy().target, base_url="http://example.com:80"))
        with self.assertRaises(ConfigError):
            GetTransport(policy().target).get("//example.com", None)

    def test_slow_trickle_hits_the_overall_deadline(self):
        # Defeats a per-read socket timeout alone; the deadline check between reads must stop it.
        with response_server() as (transport, _, _):
            started = time.monotonic()
            observation = transport.get("/trickle", None)
        self.assertEqual(observation.error, "deadline_exceeded")
        self.assertLess(time.monotonic() - started, 1.9)

    def test_https_target_that_does_not_speak_tls_is_inconclusive(self):
        # A plain-HTTP listener behind an https:// target must fail the handshake, never downgrade.
        with response_server() as (_, calls, port):
            configured = replace(policy().target, base_url=f"https://127.0.0.1:{port}", timeout_seconds=1)
            observation = GetTransport(configured).get("/ok", "synthetic-token-0001")
        self.assertEqual(observation.error, "tls_error")
        self.assertIsNone(observation.status)
        self.assertEqual(calls, [])
