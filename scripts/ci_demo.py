"""Start a loopback fixture, invoke the real CLI, and preserve its exit code."""

import argparse
import subprocess
import sys

from .demo_support import demo_environment, local_demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixed", "vulnerable"), default="fixed")
    arguments = parser.parse_args()
    try:
        with local_demo(arguments.mode):
            result = subprocess.run([sys.executable, "-m", "accessproof", "run", "configs/demo.toml", "--out", "reports/ci"],
                                    env=demo_environment(), check=False)
        return result.returncode
    except OSError:
        print("CI demo could not start; ensure local port 8765 is free", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
