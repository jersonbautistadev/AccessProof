# Writing an AccessProof policy

Start by copying `configs/demo.toml`. The configuration describes **intended access**; it is not inferred from the application. Review it with whoever owns the application's permission rules. Use known synthetic fixtures so your expected owner and sample record IDs are stable.

## Root and target

| Field | Requirement |
|---|---|
| `schema_version` | Integer `1`; boolean values are rejected |
| `suite_id` | Stable identifier for this test suite |
| `policy_version` | Nonempty human-readable revision string |
| `target.base_url` | HTTP(S) origin using a literal loopback IP, e.g. `http://127.0.0.1:8765` or `https://[::1]:8443` |
| `target.environment` | `development` or `test` |
| `target.timeout_seconds` | Integer 1–30, default 3 |
| `target.max_response_bytes` | Integer 1,024–1,048,576, default 65,536 |

Base URLs cannot contain userinfo, an application path, query, fragment, or scoped IPv6 address. `localhost` is intentionally rejected to avoid hostname resolution. Use local port forwarding to a development service if needed, and treat any forwarded service as the explicitly authorized target. The tool cannot determine whether a loopback port has been forwarded to production; that responsibility stays with the operator.

IDs start with a letter and contain up to 64 letters, digits, underscores, or hyphens. Unknown configuration keys are rejected. There are limits of 16 identities, 100 resources, and a 256 KiB configuration file.

## Identities

```toml
[identities.alice]
token_env = "ACCESSPROOF_ALICE_TOKEN"
verify_path = "/me"
subject_pointer = "/subject"
verify = { statuses = [200], json_equals = { "/subject" = "alice", "/role" = "user" } }

[identities.anonymous]
anonymous = true
```

Configure exactly one anonymous identity and at least one authenticated identity. The supplied demo has two ordinary accounts and one admin. An authenticated identity requires a token variable, verification path, and content assertions. `subject_pointer` defaults to `/subject`; its expected value must be a nonempty string, distinct across identities. Assert the role as well when a permission depends on role.

For a different API whose identity endpoint returns `{"user":{"id":"test-user-001"}}`, use `subject_pointer = "/user/id"` and assert `"/user/id" = "test-user-001"`. The config ID can still be `alice`. An API without a reliable identity endpoint needs a development-only verification endpoint or adapter before using this runner reliably.

Token environment variable names must be uppercase letters/digits/underscores, start with a letter, and be distinct. Token values must be distinct, 16–4,096 printable ASCII characters without whitespace. This version sends `Authorization: Bearer <token>` only. The runner does not perform a login flow, renew tokens, interpret JWTs, send API-key headers, or retain cookies. Supply already-issued test bearer credentials.

A missing/invalid/reused credential produces a visible inconclusive identity check. A failed identity assertion also produces an inconclusive check. Dependent permission checks do not run. Verification is required even when an identity is used only by an optional resource.

## Resources and permission matrix

```toml
[[resources]]
id = "alice-record"
path = "/records/record-alice"
owner = "alice"
positive_identity = "alice"
protected_paths = ["/private_note"]
allow = { statuses = [200], json_equals = { "/id" = "record-alice", "/owner" = "alice" } }
deny = { statuses = [401, 403], json_equals = { "/error" = "access_denied" } }
permissions = { alice = "allow", bob = "deny", admin = "allow", anonymous = "deny" }
required = true
```

`owner` records the fixture's owner or, for an admin-only function, its administrative custodian. It does not automatically grant access. `permissions` is authoritative. Both the owner and `positive_identity` must be configured authenticated identities explicitly granted `allow`.

The positive identity must successfully fetch the sample resource before its matrix is evaluated. Its response must satisfy `allow` and contain every configured protected path. This prevents a nonexistent fixture, an HTML login screen, or a partial generic response from making denied checks appear successful. The positive response is reused as the corresponding permission observation; other identities get independent requests.

Paths are literal absolute paths, with no variables, query strings, percent encoding, fragments, dot segments, repeated slashes, or backslashes. Only GET is implemented; a `method` field is rejected. For APIs using query parameters, add a suitable synthetic path-based endpoint or defer that endpoint until explicit query support is implemented.

`allow` and `deny` each require a nonempty list of statuses and at least one `json_equals` content assertion. JSON pointers use RFC 6901-style paths: `/owner`, `/user/id`, `/items/0/id`, and escapes `~1` for `/` and `~0` for `~`. The root response must be a JSON object. Expected values are strings, integers, or booleans; equality is type-strict (`true` does not equal `1`). All assertions must match.

Allowed/identity success statuses must be 2xx. Denial statuses may be `200`, `401`, `403`, or `404`. A 200 denial is accepted only when explicitly configured content matches. A verified authenticated identity receiving 401 is always inconclusive; an anonymous 401 may pass its denial contract. A denial with unknown content is inconclusive. Redirects, non-JSON, duplicate JSON keys, malformed data, compressed bodies, over-limit bodies, and transport errors are inconclusive.

`protected_paths` names fields whose **presence** would be an exposure for a denied identity. Presence counts even if the field is empty or null. Configure only fields that must be absent in a denial response; otherwise this can cause false positives. Protection is exact-path based. Wildcards, recursive key matching, and matching field values elsewhere are not implemented. Include every sensitive path relevant to this response.

## Required, omitted, and skipped checks

The runner creates one row for every declared identity on every resource. An identity omitted from `permissions` appears as `skipped / permission_not_configured`. You can intentionally skip a check with a reason instead:

```toml
# For a resource whose permissions table omits bob:
skip = { bob = "fixture not yet available" }
```

A skip cannot overlap a permission. Required skipped checks block CI. `required = false` makes all of that resource's control/permission rows optional, but they still appear. Keep this setting narrow and reviewed; declaring a check optional changes its policy fingerprint. The tool does not enumerate unknown endpoints: completeness of the resource inventory must be reviewed independently.

## Baselines

```sh
python -m accessproof run configs/demo.toml --out reports/baseline
python -m accessproof run configs/demo.toml --out reports/current --baseline reports/baseline/report.json
```

Prefer a reviewed, passing baseline kept outside the current output directory. The runner refuses to overwrite a baseline that resolves to either output file path, regardless of the baseline's filename extension. It does not sign baselines or decide whether a policy edit is legitimate. Compare policies in source control, then create a new baseline deliberately. Do not overwrite the policy or baseline while a run is in progress.
