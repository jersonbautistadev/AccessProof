"""Public synthetic credentials and a server context for local demonstrations."""

from contextlib import contextmanager
import os
import threading

from accessproof.demo import TOKEN_VARIABLES, make_server

PUBLIC_DEMO_TOKENS = {"alice": "demo-alice-token-0001", "bob": "demo-bob-token-000002", "admin": "demo-admin-token-0003"}


def demo_environment():
    environment = dict(os.environ)
    environment.update({TOKEN_VARIABLES[name]: token for name, token in PUBLIC_DEMO_TOKENS.items()})
    return environment


@contextmanager
def local_demo(mode):
    server = make_server(port=8765, mode=mode, tokens=PUBLIC_DEMO_TOKENS)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
