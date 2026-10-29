# Verification record

Verified locally on October 29, 2026 with Python 3.12.14 on Linux.

| Verification | Result |
|---|---|
| `python -m unittest discover -v` | 44 tests passed, including real loopback HTTP integration |
| `python -m scripts.walkthrough` | Expected CLI exits 1 → 0 → 1; four resolved failures, then four newly failing permissions |
| `python -m scripts.ci_demo` | Exit 0 with 18 passed logical checks |
| Configuration and baseline validation | Negative cases reject unsupported targets, policy errors, malformed baselines, and output paths that would overwrite a baseline |
| Sanitized sample reports | 18 result rows each; fixture tokens and private response values absent |
| Documentation | Relative file links checked |
| GitHub workflow | YAML structure, read-only permissions, unmasked gate command, and unconditional report-upload step inspected |
| HTML structure/privacy | Parsed successfully; no active script/embedded object tags; hostile text escaped in tests |

The HTML report has not been visually verified in a browser here because a browser executable is unavailable. The hosted GitHub Actions workflow and Windows command examples have not been executed here. Only the workflow's Python commands were run locally. Python 3.11 is the declared minimum based on the standard-library features used; this environment's executed tests used 3.12.

The seeded experiment covers two defect classes and twelve permission cases. The evaluation document records a reproducible missed leak and a deliberately incorrect policy that raises a false alarm relative to the application's real rules. No broader security or detection-accuracy claim is made.
