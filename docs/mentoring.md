# Build understanding in four increments

The working implementation is provided so you can run a complete experiment. Learn it in small changes. For each exercise, make one change, explain the expected outcome before running, verify it, and record it in a Git commit. Do not feel you need to explain every module in one sitting.

## 1. Explain the API and the access rules

Read `configs/demo.toml` beside `accessproof/demo.py`. Authentication answers “which test account supplied this token?” Authorization answers “may that account read this record or use this function?” In vulnerable mode, authentication still works; ownership and role checks are omitted.

**Exercise:** Start the corrected demo and run the policy. Find the Alice→Bob-record denial and Alice→Alice-record allowance in the report. Explain why an administrator can read both records. Then run the vulnerable variant and predict the four changed matrix cells before checking.

**Interview explanation:** “I modeled permissions explicitly rather than inferring them from responses. The same account can be authenticated successfully and still access something it should not.”

## 2. Follow one result through the runner

Read `runner.py` and the pure functions in `evaluation.py`. Bob's own record is first fetched as Bob. That verifies the fixture exists and the expected response shape is meaningful. Alice is separately verified using `/me`. Only then is Alice's request for Bob's record evaluated.

**Exercise:** Remove Bob's token from your environment and rerun. Explain why Bob's record checks become inconclusive instead of passing their expected denials. Restore it afterward. Review `test_authenticated_401_after_valid_preflight_is_inconclusive` and explain why a 401 differs from a verified 403.

**Interview explanation:** “A denial can happen because the test credentials or resource are broken. Positive controls and identity checks prevent those failures from looking like successful authorization tests.”

The synchronous runner is intentional. Fifteen requests are enough for the demo: three identity requests, three positive controls, and nine remaining permission requests. The report has eighteen logical check rows because the positive observations also satisfy three permission cells. Parallelism would add state and debugging complexity without much benefit at this size.

## 3. Improve a policy and test a missed bug

Read `test_documents_deliberately_missed_unconfigured_field_leak`. It documents a real gap rather than hiding it.

**Exercise:** Add `/unconfigured_private_field` to the protected paths of Bob's resource and make the synthetic legitimate response contain it. Update the regression test to assert that Alice's injected denied response now fails. Predict the policy fingerprint change. This needs both a legitimate fixture update and a marker update; otherwise the positive control correctly refuses to validate the changed policy.

**Interview explanation:** “This tool's coverage is limited by configured resources and assertions. I included a reproducible false negative and showed how improving the policy changes coverage.”

Read `config.py` next. The helpers keep malformed input from reaching networking, while frozen dataclasses keep the model straightforward. The dict fields are treated as immutable by convention; frozen dataclasses do not recursively freeze them. For a larger public API, use immutable mappings or defensive copies. Current code does not mutate them during a run.

## 4. Trace the CI gate and a regression

Read `reporting.py`, `__main__.py`, then `.github/workflows/accessproof.yml`. Run `python -m scripts.walkthrough` and inspect `comparison.newly_failing` in the final JSON report.

**Exercise:** Change `policy_version` in a copy of the configuration and compare against the old baseline. Explain why AccessProof refuses to claim an equivalent comparison even if all current requests pass. Then establish a separate reviewed baseline without replacing the original.

**Interview explanation:** “The CI step blocks on required failures and uncertainty. Baseline comparison highlights regressions, but an existing failure still blocks. Configuration changes are fingerprinted so different policies cannot silently be compared.”

## Questions you should be able to answer

1. Why is HTTP status alone insufficient? Give a 200 login page and a leaking 403 as examples.
2. Which authorization bug is ownership-related, and which is function-related?
3. How does the tool know Alice's token actually represents Alice?
4. What happens if the sample record is deleted?
5. Why do required skipped checks block CI?
6. Why are response bodies omitted instead of being broadly logged and redacted afterward?
7. What does the policy fingerprint cover, and what does it deliberately exclude?
8. What is one demonstrated false negative? What could cause a false positive?
9. What must change before supporting production authentication or remote targets?
10. Which parts did you understand, test, or extend yourself, and what assistance did you use?

## Suggested Git checkpoints

The archive contains no Git history. Initialize a repository locally when you are ready, review `.gitignore`, and use checkpoints such as these for your own changes:

1. Document the permission matrix and run the provided prototype.
2. Add a new synthetic resource with a test.
3. Close the demonstrated unconfigured-field gap.
4. Run and explain the CI workflow on your GitHub repository.

Do not fabricate a development history for the provided implementation. Build a truthful history of your own understanding and improvements. No files have been pushed to your GitHub account by this project setup.
