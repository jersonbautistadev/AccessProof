import type { ErrorObject } from "ajv";
import validateReport from "./generated/validate-report";

// Types mirror schema/report.schema.json (report_version 1). Values are only typed as
// Report after the generated schema validator accepts them.

export type Status = "passed" | "failed" | "inconclusive" | "skipped";

export interface AssertionCheck {
  kind: "status" | "json_equals";
  pointer?: string;
  matched: boolean;
}

export interface Evidence {
  http_status?: number | null;
  body_bytes?: number;
  json_object?: boolean;
  transport_error?: string | null;
  identity_assertions?: AssertionCheck[];
  allow_assertions?: AssertionCheck[];
  deny_assertions?: AssertionCheck[];
  protected_fields_present?: string[];
  control_diagnostic?: string;
  skip_reason?: string;
}

export interface Result {
  id: string;
  kind: "identity" | "control" | "permission";
  identity: string;
  resource: string | null;
  expected: "verified identity" | "known legitimate access" | "allow" | "deny" | "unspecified";
  status: Status;
  reason: string;
  required: boolean;
  evidence: Evidence;
}

export interface Gate {
  status: "passed" | "blocked";
  reasons: Array<"required_checks_not_passed" | "comparison_policy_changed" | "comparison_coverage_mismatch">;
  blocking_checks: string[];
}

export interface Comparison {
  status: "not_requested" | "equivalent" | "policy_changed" | "coverage_mismatch";
  baseline_fingerprint?: string;
  newly_failing: string[];
  newly_inconclusive: string[];
  resolved: string[];
  added: string[];
  removed: string[];
}

export interface Report {
  report_version: 1;
  tool_version: string;
  evaluator_version: number;
  created_at: string;
  suite_id: string;
  policy_version: string;
  policy_fingerprint: string;
  target: string;
  scope: { method: "GET"; configured_resources: number; configured_identities: number; permission_checks: number };
  summary: Partial<Record<Status, number>>;
  gate?: Gate;
  results: Result[];
  comparison: Comparison;
  limitation: string;
}

export type LoadResult = { ok: true; report: Report } | { ok: false; title: string; problems: string[] };

/** Same ceiling the CLI applies to baseline files. */
export const MAX_REPORT_BYTES = 8 * 1024 * 1024;

const shorten = (value: unknown) => {
  const text = String(value);
  return text.length > 60 ? `${text.slice(0, 57)}...` : text;
};

function describe(error: ErrorObject): string {
  const where = error.instancePath ? `"${shorten(error.instancePath)}"` : "The top level";
  switch (error.keyword) {
    case "additionalProperties":
      return `${where} has an unexpected field "${shorten(error.params.additionalProperty)}".`;
    case "required":
      return `${where} is missing "${shorten(error.params.missingProperty)}".`;
    default:
      return `${where} ${error.message ?? "is invalid"}.`;
  }
}

/** Validate already-parsed data against the report schema. */
export function checkReport(data: unknown): LoadResult {
  if (typeof data === "object" && data !== null && !Array.isArray(data)) {
    const version = (data as { report_version?: unknown }).report_version;
    if (typeof version === "number" && version > 1) {
      return {
        ok: false,
        title: `This report uses format version ${version}, which this viewer doesn't support yet.`,
        problems: ["Open it with the viewer from the AccessProof release that wrote it."],
      };
    }
  }
  if (validateReport(data)) return { ok: true, report: data as Report };
  const errors = validateReport.errors ?? [];
  const problems = [...new Set(errors.map(describe))].slice(0, 5);
  return { ok: false, title: "This file isn't a valid AccessProof report.", problems };
}

export function parseReport(text: string): LoadResult {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return {
      ok: false,
      title: "This file isn't valid JSON.",
      problems: ["Choose the report.json file that AccessProof wrote."],
    };
  }
  return checkReport(data);
}

export async function readReportFile(file: File): Promise<LoadResult> {
  if (file.size > MAX_REPORT_BYTES) {
    return {
      ok: false,
      title: "This file is larger than 8 MB.",
      problems: ["AccessProof reports are much smaller. Choose a report.json file."],
    };
  }
  return parseReport(await file.text());
}
