"""Detect, correct, rerun, and reintroduce two known authorization defects."""

import json
from pathlib import Path
import subprocess
import sys

from .demo_support import demo_environment, local_demo


def stage(mode, name, expected_exit, baseline=None):
    directory = Path("reports/walkthrough") / name
    command = [sys.executable, "-m", "accessproof", "run", "configs/demo.toml", "--out", str(directory)]
    if baseline is not None:
        command.extend(["--baseline", str(baseline)])
    with local_demo(mode):
        completed = subprocess.run(command, env=demo_environment(), check=False, capture_output=True, text=True)
    print(f"\n{name.upper()} — expected CLI exit {expected_exit}, observed {completed.returncode}", flush=True)
    print(completed.stdout, end="", flush=True)
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != expected_exit:
        raise RuntimeError("walkthrough did not produce its expected CLI result")
    (directory / "terminal.txt").write_text(completed.stdout, encoding="utf-8")
    return json.loads((directory / "report.json").read_text(encoding="utf-8"))


def main():
    try:
        vulnerable = stage("vulnerable", "vulnerable", 1)
        fixed = stage("fixed", "fixed", 0, Path("reports/walkthrough/vulnerable/report.json"))
        regression = stage("vulnerable", "regression", 1, Path("reports/walkthrough/fixed/report.json"))
        expected_bugs = {"permission:alice-record:bob", "permission:bob-record:alice",
                         "permission:admin-audit:alice", "permission:admin-audit:bob"}
        detected = {row["id"] for row in vulnerable["results"] if row["status"] == "failed"}
        valid_rows = [row for row in fixed["results"] if row["kind"] == "permission"]
        if detected != expected_bugs or any(row["status"] != "passed" for row in valid_rows):
            raise RuntimeError("fixture detection or valid-case verification failed")
        if set(regression["comparison"]["newly_failing"]) != expected_bugs:
            raise RuntimeError("regression tracking did not identify all reintroduced failures")
        evaluation = {
            "dataset": "synthetic demo only; two defect classes; not a general accuracy benchmark",
            "vulnerable_permission_cases": 12,
            "known_unauthorized_access_cases": 4,
            "detected_unauthorized_access_cases": len(detected),
            "missed_known_unauthorized_access_cases": len(expected_bugs - detected),
            "fixed_valid_permission_cases": len(valid_rows),
            "false_positives_in_fixed_matrix": sum(row["status"] == "failed" for row in valid_rows),
            "inconclusive_in_fixed_matrix": sum(row["status"] == "inconclusive" for row in valid_rows),
            "resolved_after_fix": len(fixed["comparison"]["resolved"]),
            "new_failures_after_reintroduction": len(regression["comparison"]["newly_failing"]),
            "known_miss_outside_this_matrix": "An unconfigured private field can leak without detection; reproduced in tests/test_runner.py.",
        }
        destination = Path("reports/walkthrough/evaluation.json")
        destination.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
        print("\nWalkthrough verified. Open reports/walkthrough/regression/report.html to inspect newly failing permissions.")
        return 0
    except (OSError, ValueError, RuntimeError):
        print("Walkthrough could not complete; inspect the visible results and ensure local port 8765 is free", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
