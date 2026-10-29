# Sanitized sample reports

These files are generated from an actual local execution of `python -m scripts.walkthrough` using only public synthetic fixtures. The target is `127.0.0.1:8765`.

| File | Meaning |
|---|---|
| [vulnerable.html](vulnerable.html) / [vulnerable.json](vulnerable.json) | Four seeded permission failures |
| [fixed.html](fixed.html) / [fixed.json](fixed.json) | All configured checks pass; four failures resolved |
| [regression.html](regression.html) / [regression.json](regression.json) | Reintroduced bugs highlighted as newly failing |
| [evaluation.json](evaluation.json) | Fixture counts and stated known miss |

Open HTML locally in a browser. GitHub source viewing does not execute HTML as a report. Use your own generated reports as baselines for actual work; samples document the demonstration.

The evidence excludes raw response values and credentials. Check counts include three identity checks, three resource positive controls, and twelve permission checks. The valid matrix is small; passing it does not establish application-wide security.
