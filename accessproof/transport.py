"""Bounded GET transport: literal loopback IPs, no proxies, redirects, or cookies."""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import time
from dataclasses import asdict, dataclass

from .config import Target, path, target as validate_target


@dataclass(frozen=True)
class Observation:
    status: int | None = None
    body: object = None
    error: str | None = None
    body_bytes: int = 0
    is_json: bool = False

    def evidence(self) -> dict:
        # Deliberately exclude response values, headers, and exception messages.
        return {"http_status": self.status, "body_bytes": self.body_bytes,
                "json_object": self.is_json, "transport_error": self.error}


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


class GetTransport:
    def __init__(self, target: Target):
        self.target = validate_target(asdict(target))

    def get(self, endpoint: str, token: str | None) -> Observation:
        endpoint = path(endpoint)  # Defense in depth if called outside the runner.
        host, port, scheme = self.target.address
        connection_class = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        connection = connection_class(host, port, timeout=self.target.timeout_seconds)
        status = None
        data = bytearray()
        started = time.monotonic()
        try:
            headers = {"Accept": "application/json", "Accept-Encoding": "identity", "Connection": "close"}
            if token is not None:
                headers["Authorization"] = f"Bearer {token}"
            connection.request("GET", endpoint, headers=headers)
            response = connection.getresponse()
            status = response.status
            # Redirect bodies are irrelevant; never follow Location or send credentials there.
            if 300 <= status < 400:
                return Observation(status=status, error="redirect_refused")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                return Observation(status=status, error="encoded_response_unsupported")
            while True:
                chunk = response.read1(min(8192, self.target.max_response_bytes + 1 - len(data)))
                data.extend(chunk)
                if len(data) > self.target.max_response_bytes:
                    return Observation(status=status, error="response_too_large", body_bytes=len(data))
                if time.monotonic() - started > self.target.timeout_seconds:
                    return Observation(status=status, error="deadline_exceeded", body_bytes=len(data))
                if not chunk:
                    break
            if response.length is not None and response.length > 0:
                return Observation(status=status, error="truncated_response", body_bytes=len(data))
            media_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            if media_type != "application/json" and not (media_type.startswith("application/") and media_type.endswith("+json")):
                return Observation(status=status, error="non_json_response", body_bytes=len(data))
            try:
                body = json.loads(data, object_pairs_hook=unique_keys, parse_constant=reject_constant)
            except (ValueError, UnicodeError, RecursionError):
                return Observation(status=status, error="invalid_json", body_bytes=len(data))
            if not isinstance(body, dict):
                return Observation(status=status, error="json_object_required", body_bytes=len(data))
            return Observation(status, body, body_bytes=len(data), is_json=True)
        except (TimeoutError, socket.timeout):
            return Observation(status=status, error="network_timeout", body_bytes=len(data))
        except ssl.SSLError:
            return Observation(status=status, error="tls_error", body_bytes=len(data))
        except (OSError, http.client.HTTPException):
            return Observation(status=status, error="network_error", body_bytes=len(data))
        finally:
            connection.close()
