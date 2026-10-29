"""Command-line entry point. Run from the project root: python -m accessproof."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from . import __version__
from .config import ConfigError, load_policy
from .demo import serve
from .reporting import compare, load_baseline, sanitize, terminal, write_reports
from .runner import gate_failed, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configured, GET-only authorization regression checks on loopback development targets.")
    parser.add_argument("--version", action="version", version=f"AccessProof {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="Run configured checks and write sanitized JSON/HTML reports")
    run_parser.add_argument("config", type=Path)
    run_parser.add_argument("--out", type=Path, default=Path("reports/latest"))
    run_parser.add_argument("--baseline", type=Path)
    demo_parser = commands.add_parser("demo", help="Start the synthetic loopback-only demo")
    demo_parser.add_argument("--mode", choices=("fixed", "vulnerable"), default="fixed")
    demo_parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "demo":
            serve(arguments.port, arguments.mode)
            return 0
        policy = load_policy(arguments.config)
        baseline = load_baseline(arguments.baseline) if arguments.baseline else None
        output_paths = {(arguments.out / "report.json").resolve(), (arguments.out / "report.html").resolve()}
        if arguments.baseline and arguments.baseline.resolve() in output_paths:
            raise ConfigError("baseline must not match either output file; preserve the baseline")
        if arguments.config.resolve() in output_paths:
            raise ConfigError("output must not overwrite the configuration")
        environment = dict(os.environ)
        report = run(policy, environment=environment)
        if baseline is not None:
            compare(report, baseline)
        blocked = gate_failed(report)
        secrets = [environment.get(identity.token_env, "") for identity in policy.identities if identity.token_env]
        report = sanitize(report, secrets)
        write_reports(report, arguments.out)
        print(terminal(report))
        print("Sanitized reports written: report.json and report.html")
        return 1 if blocked else 0
    except ConfigError as exc:
        print(f"AccessProof configuration error: {exc}", file=sys.stderr)
        return 2
    except OSError:
        # Do not print filesystem, network, or credential-bearing exception details.
        print("AccessProof operational error: cannot bind the local demo or write output; check the port and file permissions", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("AccessProof interrupted: run incomplete", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
