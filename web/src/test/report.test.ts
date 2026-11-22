import { describe, expect, it } from "vitest";
import formatDoc from "../../../docs/report-format.md?raw";
import { REASONS } from "../reasons";
import { checkReport, MAX_REPORT_BYTES, parseReport, readReportFile } from "../report";
import { codePointLength, dateTimeFormat, jsonEqual } from "../validator-runtime";
import { reportFile, samples } from "./fixtures";

describe("report contract", () => {
  it("accepts every published sample", () => {
    for (const sample of Object.values(samples)) expect(checkReport(structuredClone(sample)).ok).toBe(true);
  });

  it("rejects fields outside the schema's disclosure allowlist", () => {
    const report = structuredClone(samples.regression) as Record<string, unknown> & { results: Array<{ evidence: Record<string, unknown> }> };
    report.results[0]!.evidence.body = "leaked response";
    const result = checkReport(report);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.problems.join(" ")).toContain('unexpected field "body"');
  });

  it("names a missing field", () => {
    const { results: _results, ...rest } = structuredClone(samples.fixed);
    const result = checkReport(rest);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.problems).toContain('The top level is missing "results".');
  });

  it("explains a report from a newer format version", () => {
    const result = checkReport({ ...structuredClone(samples.fixed), report_version: 2 });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.title).toContain("format version 2");
  });

  it("accepts reports written before the gate field existed", () => {
    const { gate: _gate, ...legacy } = structuredClone(samples.fixed);
    expect(checkReport(legacy).ok).toBe(true);
  });

  it("refuses non-JSON and oversized files without reading them as reports", async () => {
    expect(parseReport("not json")).toMatchObject({ ok: false, title: "This file isn't valid JSON." });
    const huge = reportFile("x");
    Object.defineProperty(huge, "size", { value: MAX_REPORT_BYTES + 1 });
    expect(await readReportFile(huge)).toMatchObject({ ok: false, title: "This file is larger than 8 MB." });
  });

  it("describes every reason code that docs/report-format.md documents", () => {
    // The gate reasons table and the result reason codes table.
    const section = (start: string, end: string) => formatDoc.slice(formatDoc.indexOf(start), formatDoc.indexOf(end));
    const tables = section("## The gate", "## Results") + section("### Reason codes", "## Comparison");
    const documented = [...tables.matchAll(/^\| `([a-z_]+)` \|/gm)].map((match) => match[1]);
    expect(documented.length).toBeGreaterThan(30);
    expect(documented.filter((code) => code && !(code in REASONS))).toEqual([]);
  });
});

describe("validator runtime helpers", () => {
  it("compares JSON values deeply", () => {
    expect(jsonEqual({ a: [1, { b: 2 }] }, { a: [1, { b: 2 }] })).toBe(true);
    expect(jsonEqual({ a: 1 }, { a: 1, b: undefined })).toBe(false);
    expect(jsonEqual([1, 2], { 0: 1, 1: 2 })).toBe(false);
  });

  it("counts code points, not UTF-16 units", () => {
    expect(codePointLength("a😀")).toBe(2);
  });

  it("validates RFC 3339 date-times with an offset", () => {
    expect(dateTimeFormat.validate("2026-11-22T07:11:19.767331+00:00")).toBe(true);
    expect(dateTimeFormat.validate("2026-02-30T07:11:19Z")).toBe(false);
    expect(dateTimeFormat.validate("2026-11-22T07:11:19")).toBe(false);
    expect(dateTimeFormat.validate("2028-02-29 23:59:60Z")).toBe(true);
  });
});
