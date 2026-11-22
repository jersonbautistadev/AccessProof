# Verification record

Latest local verification: **November 22, 2026**, on Windows 11 with Python 3.15.2. Additional interpreters (3.11, 3.12, 3.13, 3.14) came from `uv` in throwaway environments.

| Verification | Result |
|---|---|
| `python -m unittest discover -v` | 53 tests passed on Python 3.11, 3.12, 3.13, 3.14, and 3.15, including real loopback HTTP integration; transport tests repeated 8 times without a flaky result |
| Branch coverage (`coverage run -m unittest discover`) | 97% of the `accessproof` package; `evaluation`, `runner`, and `transport` at 100%. CI enforces a 95% floor |
| Fault injection on new tests | Each test added on November 22 was run against a deliberately broken implementation and failed, confirming it can detect the defect it targets |
| `python -m scripts.walkthrough` | Expected CLI exits 1 → 0 → 1; four resolved failures, then four newly failing permissions. A forced stage failure exits 2, names the stage, and keeps its `terminal.txt` |
| `python -m scripts.ci_demo` | Exit 0 with 18 passed checks; `--mode vulnerable` exits 1 |
| Configuration and baseline validation | Negative cases reject unsupported targets, policy errors, invalid skip entries, malformed baselines, and output paths that would overwrite a baseline or the configuration |
| Sanitized sample and generated reports | 18 result rows each; fixture tokens and private response values absent |
| HTML report in a browser | `reports/walkthrough/regression/report.html` rendered in a Chromium-based browser: 18 rows, four rows marked "NEW FAILURE", BLOCKED badge, no scripts, no console errors |
| Packaging | `accessproof --version` works from an isolated install of the project |
| Lint and format | `ruff check` and `ruff format --check` clean with the configuration in `pyproject.toml` |
| GitHub workflow | Validated with `actionlint`; every workflow command run locally in a fresh Python 3.12 virtual environment with hash-pinned tools |

## Hosted CI

The original workflow ran successfully on hosted GitHub runners for commit `b8f7661` (November 1, 2026). The Dependabot updates to `actions/checkout` 7.0.1, `actions/setup-python` 7.1.0, and `actions/upload-artifact` 7.0.2 also passed hosted CI on their own branches. On November 22, 2026, the original workflow passed on hosted Linux runners for the `deps/github-actions`, `chore/ruff-lint`, and `test/coverage-gaps` branches. That run included the 53-test suite with the new deadline and TLS tests.

The expanded workflow (Python matrix, lint job, coverage floor, walkthrough step) has been validated locally but has **not yet run on hosted runners**. Its first hosted run will be on the pull request that introduces it. Check that run before marking the new jobs as required.

## Not verified

- HTTPS against a real TLS endpoint. The tests confirm a non-TLS listener is refused (`tls_error`) without the request reaching it, but certificate validation against a self-signed or mismatched certificate is not exercised.
- IPv6 loopback targets against a live server. The demo binds only to `127.0.0.1`.
- macOS. Linux runs only in CI; Windows was run locally.

## Scope of the evidence

The seeded experiment covers two defect classes and twelve permission cases. The evaluation document records a reproducible missed leak and a deliberately incorrect policy that raises a false alarm relative to the application's real rules. No broader security or detection-accuracy claim is made.
