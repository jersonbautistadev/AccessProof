"""Body-free reporting, fail-closed baseline comparison, and HTML escaping."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
import re
import tempfile

from . import EVALUATOR_VERSION
from .config import ConfigError, require
from .runner import gate_failed


def load_baseline(filename: str | Path) -> dict:
    try:
        require(Path(filename).stat().st_size <= 8 * 1024 * 1024, "baseline exceeds 8 MiB")
        raw = json.loads(Path(filename).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError, RecursionError):
        raise ConfigError("cannot read baseline: expected an AccessProof JSON report") from None
    require(isinstance(raw, dict) and type(raw.get("report_version")) is int and raw["report_version"] == 1,
            "baseline: unsupported report format")
    require(type(raw.get("evaluator_version")) is int and raw["evaluator_version"] == EVALUATOR_VERSION,
            "baseline: incompatible evaluator version")
    require(isinstance(raw.get("policy_fingerprint"), str)
            and re.fullmatch(r"[0-9a-f]{64}", raw["policy_fingerprint"]) is not None,
            "baseline: missing policy fingerprint")
    require(isinstance(raw.get("results"), list) and bool(raw["results"]), "baseline: missing results")
    ids = []
    for result in raw["results"]:
        require(isinstance(result, dict) and isinstance(result.get("id"), str)
                and re.fullmatch(r"(?:identity|control|permission):[a-zA-Z][a-zA-Z0-9_-]{0,63}(?::[a-zA-Z][a-zA-Z0-9_-]{0,63})?", result["id"]) is not None,
                "baseline: invalid check ID")
        require(isinstance(result.get("status"), str) and result["status"] in {"passed", "failed", "inconclusive", "skipped"}, "baseline: invalid check status")
        ids.append(result["id"])
    require(len(ids) == len(set(ids)), "baseline: duplicate check IDs")
    return raw


def compare(report: dict, baseline: dict) -> None:
    previous = {result["id"]: result["status"] for result in baseline["results"]}
    current = {result["id"]: result["status"] for result in report["results"]}
    comparison = report["comparison"]
    comparison["baseline_fingerprint"] = baseline["policy_fingerprint"]
    comparison["added"] = sorted(current.keys() - previous.keys())
    comparison["removed"] = sorted(previous.keys() - current.keys())
    if report["policy_fingerprint"] != baseline["policy_fingerprint"]:
        comparison["status"] = "policy_changed"
        return
    if current.keys() != previous.keys():
        comparison["status"] = "coverage_mismatch"
        return
    comparison["status"] = "equivalent"
    comparison["newly_failing"] = sorted(key for key, status in current.items() if status == "failed" and previous[key] != "failed")
    comparison["newly_inconclusive"] = sorted(key for key, status in current.items() if status == "inconclusive" and previous[key] != "inconclusive")
    comparison["resolved"] = sorted(key for key, status in current.items() if status == "passed" and previous[key] in {"failed", "inconclusive"})


def sanitize(report: dict, secrets: list[str]) -> dict:
    # Allowlisted evidence is the primary protection. Literal secret redaction is a second layer.
    secrets = sorted({secret for secret in secrets if secret}, key=len, reverse=True)

    # These fields contain engine-owned constants, never arbitrary input or response data.
    trusted_fields = {"status", "reason", "kind", "expected", "transport_error", "control_diagnostic", "method", "limitation"}

    def clean(value, field=None):
        if isinstance(value, str):
            if field not in trusted_fields:
                for secret in secrets:
                    value = value.replace(secret, "[REDACTED]")
            return "".join(char for char in value if ord(char) >= 32 and ord(char) != 127)
        if isinstance(value, dict):
            return {key: clean(item, key) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item, field) for item in value]
        return value

    return clean(report)


def terminal(report: dict) -> str:
    lines = [f"AccessProof | {report['suite_id']} | policy {report['policy_version']}",
             f"Target: {report['target']} | GET only | fingerprint {report['policy_fingerprint'][:12]}"]
    for result in report["results"]:
        required = "required" if result["required"] else "optional"
        lines.append(f"{result['status'].upper():12} {result['id']} | expected={result['expected']} | {required} | {result['reason']}")
    summary = " | ".join(f"{status}: {report['summary'].get(status, 0)}" for status in ("passed", "failed", "inconclusive", "skipped"))
    lines.extend([summary, f"Comparison: {report['comparison']['status']}"])
    for name in ("newly_failing", "newly_inconclusive", "resolved", "added", "removed"):
        if report["comparison"][name]:
            lines.append(f"{name}: {', '.join(report['comparison'][name])}")
    lines.append("Gate: BLOCKED" if gate_failed(report) else "Gate: PASSED")
    lines.append(report["limitation"])
    return "\n".join(lines)


def render_html(report: dict) -> str:
    escape = lambda value: html.escape(str(value), quote=True)
    rows = []
    newly_failing = set(report["comparison"]["newly_failing"])
    for result in report["results"]:
        observed = f"{result['status']} — {result['reason']}"
        if result["id"] in newly_failing:
            observed = "NEW FAILURE: " + observed
        cells = [result["id"], result["identity"], result["resource"] or "—", result["expected"],
                 observed, "required" if result["required"] else "optional"]
        content = "".join(f"<td>{escape(cell)}</td>" for cell in cells)
        evidence = escape(json.dumps(result["evidence"], indent=2, ensure_ascii=True))
        rows.append(f'<tr class="{escape(result["status"])}">{content}<td><details><summary>Sanitized evidence</summary><pre>{evidence}</pre></details></td></tr>')
    summary = " · ".join(f"{status}: {report['summary'].get(status, 0)}" for status in ("passed", "failed", "inconclusive", "skipped"))
    comparison = escape(json.dumps(report["comparison"], indent=2))
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>AccessProof — {escape(report['suite_id'])}</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;margin:0;background:#f3f6fb;color:#17263d}}main{{max-width:1500px;margin:auto;padding:32px}}h1{{margin-bottom:4px}}p{{max-width:1050px}}.card{{background:white;border:1px solid #c8d3e4;border-radius:12px;padding:20px;margin:20px 0;overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #dce3ef;vertical-align:top}}th{{background:#e8eef8}}.failed td:first-child{{border-left:5px solid #b32424}}.inconclusive td:first-child{{border-left:5px solid #9a5b00}}.passed td:first-child{{border-left:5px solid #147449}}.skipped td:first-child{{border-left:5px solid #60718a}}pre{{white-space:pre-wrap;word-break:break-word;font-size:12px}}code{{word-break:break-all}}summary{{cursor:pointer}}.badge{{font-weight:700;font-size:19px}}</style></head>
<body><main><h1>AccessProof</h1><p>Configured authorization regression testing</p>
<section class="card"><div class="badge">{'BLOCKED' if gate_failed(report) else 'PASSED'}</div>
<p>{escape(summary)}</p><p>Suite: {escape(report['suite_id'])} · Policy: {escape(report['policy_version'])} · Target: {escape(report['target'])} · GET only</p>
<p>Generated: {escape(report['created_at'])}</p><p>Policy fingerprint: <code>{escape(report['policy_fingerprint'])}</code></p>
<p>{escape(report['limitation'])}</p><p>Only declared identities, resources, and assertions were tested. Evidence excludes response bodies, header values, tokens, and expected content values. All times are UTC.</p></section>
<section class="card"><h2>Regression comparison: {escape(report['comparison']['status'])}</h2><pre>{comparison}</pre></section>
<section class="card"><h2>Results</h2><table><thead><tr><th>Check</th><th>Identity</th><th>Resource</th><th>Expected</th><th>Observed</th><th>Gate</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
</main></body></html>'''


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_reports(report: dict, directory: str | Path) -> None:
    directory = Path(directory)
    atomic_write(directory / "report.json", json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    atomic_write(directory / "report.html", render_html(report))
