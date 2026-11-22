# Roadmap proposal

This is a **proposal**. The order depends on one decision only the project owner can make:

> **[OPEN QUESTION]** Is AccessProof staying a portfolio demonstration, or becoming a tool other teams run against their own development APIs? The proposal below assumes the second, at a small scale, while keeping v0.1's safety stance: GET only by default, explicit targets, and no stored response bodies. If it stays a portfolio piece, items 1–3 alone make a good v0.2.

Items are prioritized with MoSCoW and ordered by value against effort. Effort is a relative size (S, M, L), not a time commitment.

## v0.2: Must

**1. Clearer comparison wording in reports (S). Done:** reports now record a `gate` verdict and show a plain-language comparison headline. See [report-format.md](report-format.md). When the gate is blocked, the HTML and terminal reports currently say "Regression comparison: equivalent". That means "the baseline is comparable", but readers take it as "nothing changed".
- *Given* a comparable baseline with newly failing checks, *when* the report renders, *then* the heading states the regression count (for example "4 new failures against a comparable baseline") and the raw `status` value stays in the JSON unchanged.

**2. JSON arrays at the root (M).** List endpoints are a common place for object-level leaks (`GET /records` returning other users' rows).
- *Given* a resource configured as a collection with an ownership pointer (for example `/owner`), *when* a non-admin identity receives an element owned by someone else, *then* the check fails with a new reason such as `foreign_items_exposed`.
- The evidence records only counts and pointers, never item values.
- Empty lists, non-object items, and oversized lists are inconclusive.

**3. Query-parameter resource IDs (S–M).** This supports APIs shaped like `/records?id=record-bob`.
- *Given* a path with explicitly listed query keys, *when* the policy loads, *then* only those keys are accepted, and values follow the same character rules as paths.
- Any key that looks like a credential (`token`, `key`, `secret`, `password`, `auth`) is rejected.
- Query strings take part in the fingerprint.

## v0.3: Should

**4. Static cookie sessions (M).** Many development apps authenticate with a session cookie rather than a bearer token.
- Read the cookie value from an environment variable and send it as a `Cookie` header on every request.
- Keep the current rule of no cookie jar and no accepting `Set-Cookie`.
- Redact the cookie value exactly like tokens.

**5. Non-loopback development targets (L, design first).** `docs/architecture.md` already lists the prerequisites: an exact host/IP allowlist, DNS-resolution pinning, proxy rules, TLS behavior, and credential-forwarding rules. Start with an ADR and a time-boxed spike, plus a test against a real TLS endpoint, which `docs/validation.md` lists as not yet verified.

## Later: Could

- **Signed or tamper-evident baselines (M):** for example an HMAC keyed by a CI secret, so a baseline file edited in a pull request is detected.
- **Concurrent execution (S–M):** not valuable until policies grow past a few hundred checks.
- **Write and delete requests (L):** needs disposable fixtures, cleanup, idempotency, and state isolation designed first. See `docs/architecture.md`.
- **OIDC login and production authentication flows (L).**

## Won't (for now)

Dashboards, automatic endpoint discovery, AI features, database storage, and non-JSON APIs. Each one widens the scope beyond "check a reviewed permission matrix", and none of them is needed for that job.

## Cross-cutting for every item

- New behavior needs tests that fail against a broken implementation (see `docs/validation.md`).
- Coverage stays above the CI floor.
- Policy schema changes bump `schema_version`; evaluator changes bump `EVALUATOR_VERSION`, so old baselines are refused rather than compared.
- Record each change in `CHANGELOG.md`.
