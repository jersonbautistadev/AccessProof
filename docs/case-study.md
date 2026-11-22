# Case study: AccessProof

**Live viewer:** https://accessproof-iota.vercel.app
**Code:** this repository, release [0.2.0](https://github.com/jersonbautistadev/AccessProof/releases/tag/v0.2.0)

## The problem

The most common serious API flaw is not exotic. A backend change drops an ownership check, and one user can read another user's record. Or an admin-only endpoint loses its role check. OWASP ranks these as API1 (broken object-level authorization) and API5 (broken function-level authorization). Both pass ordinary functional tests, because the legitimate user's request still works.

Catching them needs a test that knows the *intended* permissions and asks, for every identity and resource: should this be allowed, and was it? It also has to be trustworthy enough to block a merge, without becoming a new source of leaked data.

## Goals and constraints

- **Explicit, reviewable intent.** Permissions live in a small TOML policy (resources × identities: allow or deny), not inferred from responses.
- **No false comfort.** A denial only counts if the test identity and the resource are known to work.
- **Safe evidence.** Reports go into CI artifacts and pull requests, so they must never contain response bodies or credentials.
- **A real CI gate,** with regressions visible against a baseline.
- **Small and auditable.** The Python tool has no runtime dependencies and targets only explicit loopback development environments, with GET requests only.

## Key decisions

**1. Prerequisites before verdicts.** A 403 proves nothing if Alice's token is expired or the record doesn't exist. So every run first verifies each identity against `/me`, then fetches each resource as a known-legitimate user (a *positive control*). Only then is the matrix judged. If a prerequisite fails, the dependent checks are *inconclusive*, never passed. An authenticated 401 is also inconclusive: it shows the credential failed, not that authorization worked.

**2. Status codes are not enough.** A 200 can be a login page, and a 403 can still carry private data. Each resource declares an allow contract, a deny contract (status plus JSON values), and *protected fields*. A denied identity fails if any protected field appears, whatever the status code.

**3. Evidence by allowlist, not redaction.** Responses are inspected in memory. Reports record only what the engine chooses to emit: status, byte count, which assertions matched, and which protected fields were present. A strict JSON Schema lists every permitted field and is enforced in tests, so a change that tried to add a response body to the report would fail CI.

**4. Comparisons that can't lie.** Baselines are compared only when a SHA-256 fingerprint of the normalized policy matches. A changed policy or a different set of checks blocks the gate instead of producing a misleading "no regressions". Every required check must pass, even if it was already failing in the baseline.

**5. The gate is recorded, not re-derived.** `report.json` stores the gate verdict that set the exit code. The viewer displays it rather than re-implementing the rule in JavaScript, so the two can't disagree. Reports written before the field existed say "not recorded" instead of guessing.

**6. A viewer that treats reports as untrusted.** The React and TypeScript viewer runs entirely in the browser. Every file is validated against the schema before display. The page runs under a strict Content Security Policy with no inline scripts, no `eval`, and no network access, so the schema validator is compiled at build time because Ajv's runtime compiler needs `eval`. The permission matrix is drawn as an access plan: rooms (resources), keycards (identities), and doors that are locked, opened, or breached. A console-style panel shows the evidence.

## Results

- **Detection on the bundled demo:** all 4 seeded unauthorized-access cases, spanning 2 defect classes, are caught. The corrected 12-case matrix has 0 false failures and 0 inconclusive cases. Reintroducing the bugs reports exactly those 4 checks as newly failing. This is a small synthetic fixture, not a general detection rate.
- **Tests:** 63 Python tests at 97% branch coverage, and 27 viewer tests. Key tests were checked by deliberately breaking the code they protect and confirming they fail.
- **CI:** tests on Python 3.11–3.14, lint, a coverage floor, the full demo walkthrough, and the viewer build. All are required by branch protection. Dependencies are pinned, CI tools are hash-pinned, and Dependabot waits 14 days before proposing a release.
- **Delivery:** the viewer is deployed on Vercel with security headers. Pull requests get private preview deployments.

## Limits, stated plainly

- **A demonstrated false negative.** A leaked field that isn't configured as protected passes. A test reproduces this on purpose.
- **A wrong policy produces wrong alarms.** AccessProof checks the policy you give it; it can't decide what the business rules should be.
- **No discovery.** Undeclared endpoints are outside scope.
- **Narrow request support.** Only GET requests, JSON-object responses, pre-issued bearer tokens, and loopback targets are supported.

See [evaluation.md](evaluation.md) for the full list.

## What to do differently, and next

- **Collection endpoints** (JSON arrays at the root) are where many real object-level leaks appear, such as `GET /records` returning other users' rows. That is the next feature on the [roadmap](roadmap.md).
- **Schema-based response checks** would close the documented false negative: flag any field not expected for a denied identity, not just the configured ones.
- **The report contract would come first.** Defining `report.json` as a schema earlier would have avoided retrofitting the gate field later.
