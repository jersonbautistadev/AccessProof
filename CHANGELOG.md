# Changelog

All notable changes to AccessProof are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

The report format gains one additive field (`gate`), so `report_version` stays `1`. The CLI options, policy schema, and exit codes are unchanged.

### Added
- `report.json` records the gate verdict: `gate.status` (`passed` or `blocked`), `gate.reasons`, and `gate.blocking_checks`. It is the same decision that sets the exit code, so readers no longer re-derive it.
- A strict JSON Schema for `report.json` (`schema/report.schema.json`) that doubles as a disclosure allowlist, and `docs/report-format.md` with field meanings, all 30 reason codes, and compatibility rules. Contract tests validate generated reports and the published samples against it, and fail if a reason code is undocumented.
- MIT license, declared in `pyproject.toml`.
- Tests for previously unexercised paths: a leak that omits the protected field (`unexpected_access_verified`), overlapping allow/deny contracts (`ambiguous_assertions`), the overall response deadline, refusal of a non-TLS listener behind an `https://` target, skip-entry validation, regression markers in HTML and terminal output, and the `demo`, overwrite-protection, and Ctrl+C CLI paths. 44 → 53 tests; package branch coverage 93% → 97%.
- CI: a Python 3.11 / 3.13 / 3.14 test matrix, a `ruff` lint and format job, a 95% branch-coverage floor, and the full walkthrough as a gate. CI-only tools are installed from hash-pinned `ci/requirements.txt`.
- `docs/roadmap.md` with a proposed order for the deferred features.

### Changed
- Terminal and HTML reports state the comparison outcome in plain language ("Compared with baseline: 4 newly failing") instead of the bare `equivalent` status, and list the gate's reasons.
- Sample reports in `docs/samples/` regenerated with the gate field.
- GitHub Actions updated: `actions/checkout` 7.0.1, `actions/setup-python` 7.1.0, `actions/upload-artifact` 7.0.2.
- CI runs on pushes to `main` and on pull requests instead of on every push, so pull request branches are no longer checked twice.
- Code formatted with `ruff format`. Lint fixes only, with no behavior change.
- The walkthrough keeps each stage's `terminal.txt` even when the stage misbehaves, and names the failing stage.
- `docs/validation.md` and the README now reflect hosted CI runs, Windows, and Python 3.11–3.15.

## [0.1.0] - 2026-10-29

### Added
- Initial release: strict TOML policy validation and fingerprinting, loopback-only GET transport, identity and positive-control prerequisites, permission-matrix evaluation, sanitized JSON/HTML/terminal reports, policy-aware baseline comparison, a synthetic demo with vulnerable and fixed modes, the walkthrough and CI helpers, and the GitHub Actions workflow.

[Unreleased]: https://github.com/jersonbautistadev/AccessProof/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jersonbautistadev/AccessProof/releases/tag/v0.1.0
