# Report format (`report.json`)

`report.json` is AccessProof's public output contract. The CLI writes it, CI archives it, baselines are made from it, and the report viewer reads it. The machine-readable definition is [schema/report.schema.json](../schema/report.schema.json) (JSON Schema 2020-12). This page explains what the fields mean and how the format may change.

The schema is strict: every field and every evidence key is listed, and anything else is rejected. That makes it a disclosure allowlist as well as a format description. A change that would put response bodies, headers, or credentials into a report fails schema validation in the test suite.

## Top-level fields

| Field | Meaning |
|---|---|
| `report_version` | Format version. Currently `1`. See [Compatibility](#compatibility) |
| `tool_version`, `evaluator_version` | AccessProof version, and the version of the pass/fail rules. Baselines from another evaluator version are refused |
| `created_at` | UTC timestamp, ISO 8601 |
| `suite_id`, `policy_version` | From the policy file |
| `policy_fingerprint` | SHA-256 of the normalized policy. Two reports are comparable only when fingerprints match |
| `target` | Normalized base URL of the tested application |
| `scope` | Method (`GET`) and the configured resource, identity, and permission-check counts |
| `summary` | Number of results per status. Statuses with no results are omitted |
| `gate` | The recorded CI decision. See below |
| `results` | One entry per check, in execution order: identities, then positive controls, then the permission matrix |
| `comparison` | Outcome of `--baseline` comparison, or `not_requested` |
| `limitation` | The fixed statement that passing configured checks does not prove the whole application is secure |

## The gate

```json
"gate": { "status": "blocked", "reasons": ["required_checks_not_passed"], "blocking_checks": ["permission:bob-record:alice"] }
```

`gate.status` is exactly what decided the CLI exit code: `passed` means exit `0`, `blocked` means exit `1`. **Readers must display it, not re-derive it.** Re-implementing the rule elsewhere invites two answers to the same question.

| Reason | Meaning |
|---|---|
| `required_checks_not_passed` | At least one required check is failed, inconclusive, or skipped. `blocking_checks` lists them in result order |
| `comparison_policy_changed` | A baseline was given but its policy fingerprint differs |
| `comparison_coverage_mismatch` | A baseline was given with the same policy but a different set of checks |

Reports written before this field existed have no `gate`. A reader should say the verdict was not recorded and suggest regenerating the report, rather than guessing.

## Results

Each result has a stable `id`, which is the key used for baseline comparison:

| `kind` | `id` form | `expected` |
|---|---|---|
| `identity` | `identity:<identity>` | `verified identity` |
| `control` | `control:<resource>` | `known legitimate access` |
| `permission` | `permission:<resource>:<identity>` | `allow`, `deny`, or `unspecified` |

`status` is one of `passed`, `failed`, `inconclusive`, or `skipped`. `required: false` marks a result that is shown but cannot block the gate. Identity checks are always required.

### Evidence

Evidence is body-free by construction. It never holds response values, header values, tokens, or expected assertion values.

| Key | Meaning |
|---|---|
| `http_status`, `body_bytes`, `json_object` | What came back, without the content |
| `transport_error` | Transport reason code, or `null` |
| `identity_assertions`, `allow_assertions`, `deny_assertions` | Which configured assertions matched. Each item has `kind` (`status` or `json_equals`), `matched`, and, for `json_equals`, the JSON pointer checked |
| `protected_fields_present` | JSON pointers of configured protected fields found in the response |
| `control_diagnostic` | Why a positive control was not verified |
| `skip_reason` | The policy's stated reason for an explicit skip |

Evidence is `{}` when no request was made, for example when a credential was missing.

### Reason codes

`reason` is a machine-readable code. New codes may be added without changing `report_version`, so readers must show unknown codes as they are instead of failing.

| Code | Status it accompanies | Meaning |
|---|---|---|
| `identity_verified` | passed | The credential authenticated as the configured subject and role |
| `identity_not_verified` | inconclusive | The identity response did not match the configured subject or role |
| `credential_missing` | inconclusive | The credential environment variable is unset or empty |
| `credential_invalid` | inconclusive | The credential has an invalid length or characters |
| `credential_reused_across_identities` | inconclusive | Two identities share one credential value |
| `expected_access_verified` | passed | Allowed access returned the configured legitimate response with every protected field |
| `expected_denial_verified` | passed | Denied access returned the configured denial response |
| `unexpected_access_verified` | failed | A denied identity received the legitimate response |
| `protected_fields_exposed` | failed | A denied identity's response contained a protected field, whatever its status code |
| `expected_access_denied` | failed | An allowed identity was refused while the positive control worked |
| `control_identity_not_verified` | inconclusive | The positive control's identity failed verification |
| `positive_control_not_verified` | inconclusive | The known-legitimate request did not verify, so this resource's matrix cannot be judged |
| `identity_not_verified` | inconclusive | (On permission checks) this identity failed verification |
| `authentication_rejected` | inconclusive | An authenticated request got `401`, which is not proof of an authorization denial |
| `ambiguous_assertions` | inconclusive | The response matched both the allow and the deny contract |
| `legitimate_response_not_verified` | inconclusive | Allowed access returned something other than the legitimate contract |
| `response_matches_neither_contract` | inconclusive | Denied access returned something matching neither contract |
| `server_error` | inconclusive | Status `5xx`, or no status |
| `explicit_skip` | skipped | The policy skips this identity with a stated reason |
| `permission_not_configured` | skipped | The policy states no permission for this identity |
| `redirect_refused` | inconclusive | The response was a redirect. Redirects are never followed |
| `encoded_response_unsupported` | inconclusive | The response used a content encoding |
| `response_too_large` | inconclusive | The response exceeded `max_response_bytes` |
| `deadline_exceeded` | inconclusive | The response exceeded the overall time limit |
| `truncated_response` | inconclusive | The body was shorter than its declared length |
| `non_json_response` | inconclusive | The response was not JSON |
| `invalid_json` | inconclusive | The JSON was malformed, had duplicate keys, or used non-standard constants |
| `json_object_required` | inconclusive | The JSON root was not an object |
| `network_timeout` | inconclusive | A socket operation timed out |
| `tls_error` | inconclusive | The TLS handshake or certificate check failed |
| `network_error` | inconclusive | The connection failed |

## Comparison

| `comparison.status` | Meaning | Blocks the gate |
|---|---|---|
| `not_requested` | No `--baseline` given | No |
| `equivalent` | Same policy and same checks. `newly_failing`, `newly_inconclusive`, and `resolved` list the differences | Only through the checks themselves |
| `policy_changed` | Fingerprints differ, so results are not comparable | Yes |
| `coverage_mismatch` | Same policy, different set of checks. `added` and `removed` list them | Yes |

`equivalent` means the two reports can be compared, not that nothing changed. The terminal and HTML reports therefore show a plain-language headline such as "Compared with baseline: 4 newly failing".

## Compatibility

The format follows these rules:

- **No version change** for additive changes: a new optional field, a new reason code, or a new evidence key. The schema is updated in the same change.
- **`report_version` increases** for anything that could mislead an existing reader: removing or renaming a field, changing a field's type or meaning, or changing what a status means.
- **`evaluator_version` increases** when the pass/fail rules change. Old baselines are then refused rather than compared.

Readers should validate against the schema matching the report's `report_version`, display `gate` rather than recompute it, and tolerate unknown reason codes. Report contents come from developer-controlled policies and editable baseline files, so a reader must escape every value it displays.
