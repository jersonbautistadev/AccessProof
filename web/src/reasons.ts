// Plain-language reason codes, mirroring docs/report-format.md. A test checks that
// every code documented there has an entry here. Unknown codes are shown as-is,
// because new codes may appear without a report_version change.

export const REASONS: Record<string, string> = {
  identity_verified: "The credential authenticated as the configured subject and role.",
  identity_not_verified: "The identity could not be verified, so its checks can't be judged.",
  credential_missing: "The credential environment variable was unset or empty.",
  credential_invalid: "The credential had an invalid length or characters.",
  credential_reused_across_identities: "Two identities shared one credential value.",
  expected_access_verified: "Allowed access returned the legitimate response, with every protected field.",
  expected_denial_verified: "Denied access returned the configured denial response.",
  unexpected_access_verified: "A denied identity received the legitimate response.",
  protected_fields_exposed: "A denied identity's response contained a protected field.",
  expected_access_denied: "An allowed identity was refused while the positive control worked.",
  control_identity_not_verified: "The positive control's identity failed verification.",
  positive_control_not_verified: "The known-legitimate request didn't verify, so this resource can't be judged.",
  authentication_rejected: "An authenticated request got 401, which doesn't prove an authorization denial.",
  ambiguous_assertions: "The response matched both the allow and the deny contract.",
  legitimate_response_not_verified: "Allowed access returned something other than the legitimate response.",
  response_matches_neither_contract: "Denied access returned something matching neither contract.",
  server_error: "The server returned a 5xx status, or no status.",
  explicit_skip: "The policy skips this identity, with a stated reason.",
  permission_not_configured: "The policy states no permission for this identity.",
  redirect_refused: "The response was a redirect. Redirects are never followed.",
  encoded_response_unsupported: "The response used a content encoding.",
  response_too_large: "The response exceeded the configured size limit.",
  deadline_exceeded: "The response exceeded the overall time limit.",
  truncated_response: "The body was shorter than its declared length.",
  non_json_response: "The response wasn't JSON.",
  invalid_json: "The JSON was malformed, had duplicate keys, or used non-standard constants.",
  json_object_required: "The JSON root wasn't an object.",
  network_timeout: "A network operation timed out.",
  tls_error: "The TLS handshake or certificate check failed.",
  network_error: "The connection failed.",
  required_checks_not_passed: "At least one required check didn't pass.",
  comparison_policy_changed: "The policy changed since the baseline.",
  comparison_coverage_mismatch: "The baseline has a different set of checks.",
};

export function describeReason(code: string): string {
  return REASONS[code] ?? `Reason code "${code}".`;
}
