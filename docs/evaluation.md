# Evaluation and honest limits

## Repeatable fixture experiment

Run `python -m unittest discover -v`, then `python -m scripts.walkthrough`. The walkthrough records results in `reports/walkthrough/evaluation.json`. The included sample evaluation is an actual local run, not an estimated accuracy score.

The configured matrix has 12 permission cases: five permitted requests and seven expected denials. The vulnerable demo introduces two defect classes: absent ownership enforcement and absent administrator-role enforcement. Those omissions produce four unauthorized-access cases. The three anonymous denial cases still work in both variants.

| Fixture set | Ground truth | Observed outcome |
|---|---|---|
| Vulnerable cross-owner reads | Alice reads Bob's record; Bob reads Alice's record: 2 bugs | Both detected as failed |
| Vulnerable admin-only function | Alice and Bob read the audit endpoint: 2 bugs | Both detected as failed |
| Other cases in vulnerable matrix | 8 valid permission cases | All 8 passed |
| Corrected matrix | 12 valid permission cases | All 12 passed; 0 false failures and 0 inconclusive cases |
| Reintroduced bugs | Same four access violations under an equivalent policy | All four identified as newly failing |

Identity verification adds three checks, and resource positive controls add three more. Reports therefore contain **18 rows**, while the permission experiment contains **12 cases**. Reused positive-control observations are not additional independent measurements. Four detected cases exercise only two seeded defect classes; do not present them as four unrelated vulnerability discoveries or a general 100% detection rate.

## Fault cases with deterministic expectations

Automated tests cover the following independently of the walkthrough:

| Injected condition | Expected tool behavior |
|---|---|
| Missing, short, control-character, or reused credentials | Inconclusive identity check; dependent checks remain visible |
| Valid token represents the wrong subject or role | Inconclusive identity check |
| Authenticated 401 after a successful identity check | Inconclusive; not counted as a successful denial |
| All business requests return denial responses | Positive controls fail; no permission row is reassuringly passed |
| Known resource disappears | Entire resource matrix becomes inconclusive |
| Generic 200 login message or wrong record | Inconclusive; status alone is insufficient |
| Explicit configured JSON denial with HTTP 200 | Passed when denial content matches and protected fields are absent |
| HTTP 403 containing a configured private field | Failed exposure |
| Known legitimate non-control actor unexpectedly receives a verified denial | Failed permitted-access case |
| Connection failure, timeout, redirect, oversized body, truncated body | Visible inconclusive outcome |
| Non-JSON, invalid JSON, duplicate keys, unsupported compression | Visible inconclusive outcome |
| Required check omitted or explicitly skipped | Visible skipped row; gate blocks |
| Same fingerprint but missing baseline rows | Coverage mismatch; gate blocks |
| Changed policy with all current rows passing | Policy changed; comparison not claimed; gate blocks |
| Hostile HTML in metadata | Escaped; no active script in the report |

## Reproduced missed bug

`test_documents_deliberately_missed_unconfigured_field_leak` injects a denied response containing:

```json
{"error":"access_denied","unconfigured_private_field":"MISSED_LEAK"}
```

The policy protects `/private_note`, not `/unconfigured_private_field`. The denial status and configured error content match, so the tool passes this check. **This is a demonstrated false negative.** It motivates careful sensitive-field inventory or future schema-based response validation. The leaked value is still excluded from reports, but report privacy does not make the target's leak safe.

## False positives and ambiguous outcomes

No false failure was observed in the corrected 12-case demo matrix. That statement applies only to this fixture. A wrong permission policy can flag intended application behavior: if Alice is mistakenly configured to have admin access, the corrected application's legitimate 403 becomes an expected-access failure. A test reproduces that policy error. The tool cannot decide which business policy is correct.

The protected-path rule flags a field even when its value is null or empty. A configured field that is allowed in error responses could therefore trigger a false positive. The fixture uses fields that must be absent on denial. Incorrect ownership metadata, unstable fixtures, stale identity assertions, and changing response contracts can also produce alarms or inconclusive results. Review the evidence and policy before calling a finding a vulnerability.

## Remaining limitations

- No endpoint discovery: undeclared endpoints are outside scope. Missing identities on a declared resource do appear as skipped rows.
- Only explicit, path-based, GET JSON-object responses and pre-issued bearer credentials are supported. No writes, pagination exploration, root arrays, cookies, login flows, OIDC, GraphQL operations, or query parameters.
- Exact JSON paths and scalar equality do not cover arbitrary business rules, nested wildcards, field-level permissions beyond configured markers, timing leaks, headers, encoded secrets, or inference attacks.
- Authentication checks run once at the start. A token can expire later; a 401 remains inconclusive. A changed identity behind the same token that still receives a 403 may be harder to distinguish.
- A resource positive control runs before the matrix. Resources or permissions can change afterward. There is no snapshot or transaction isolation.
- A response too large or malformed to evaluate is inconclusive. Any disclosure hidden inside unsupported content may be missed as a specific leak, although the required check still blocks CI.
- Bodies are byte-limited and socket operations have timeouts. Deadline checks between reads do not impose an exact total runtime limit; CI also has a job timeout.
- Baselines are unsigned, developer-controlled files. A policy hash establishes configuration equality, not report authenticity or the completeness of testing.
- A loopback address can be forwarded elsewhere. The runner cannot certify that the selected target contains only synthetic data.
- The current demo does not reproduce production identity providers, databases, multi-tenant hierarchies, distributed caches, or race conditions.
- Tests were executed with Python 3.12 on Linux here. Windows command examples and hosted GitHub Actions have not been run in this environment.

Use the project to demonstrate reproducible authorization regression testing and careful handling of uncertainty. Do not present a green report as an application security certificate.
