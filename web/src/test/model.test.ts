import { describe, expect, it } from "vitest";
import regressionHtml from "../../../docs/samples/regression.html?raw";
import { buildPlan, comparisonHeadline, doorState, verdict } from "../model";
import type { Result } from "../report";
import { load, samples } from "./fixtures";

const check = (status: Result["status"], expected: Result["expected"]) =>
  ({ id: "permission:r:i", kind: "permission", identity: "i", resource: "r", expected, status, reason: "x", required: true, evidence: {} }) as Result;

describe("access plan", () => {
  it("maps every status and expectation to a door state", () => {
    expect(doorState(check("passed", "allow"))).toBe("opened");
    expect(doorState(check("passed", "deny"))).toBe("locked");
    expect(doorState(check("failed", "deny"))).toBe("breached");
    expect(doorState(check("failed", "allow"))).toBe("refused");
    expect(doorState(check("inconclusive", "deny"))).toBe("unverified");
    expect(doorState(check("skipped", "unspecified"))).toBe("unchecked");
  });

  it("lays out keycards with the anonymous identity last, and one door per permission", () => {
    const plan = buildPlan(load(samples.regression));
    expect(plan.keycards.map((card) => card.id)).toEqual(["admin", "alice", "bob", "anonymous"]);
    expect(plan.keycards[3]?.identityCheck).toBeUndefined();
    expect(plan.rooms.map((room) => room.id)).toEqual(["admin-audit", "alice-record", "bob-record"]);
    const breached = plan.rooms.flatMap((room) => room.doors).filter((door) => door?.state === "breached");
    expect(breached.map((door) => door?.check.id).sort()).toEqual([
      "permission:admin-audit:alice",
      "permission:admin-audit:bob",
      "permission:alice-record:bob",
      "permission:bob-record:alice",
    ]);
    expect(breached.every((door) => door?.change === "new")).toBe(true);
  });

  it("marks resolved doors as fixed", () => {
    const doors = buildPlan(load(samples.fixed)).rooms.flatMap((room) => room.doors);
    expect(doors.filter((door) => door?.change === "fixed")).toHaveLength(4);
    expect(doors.every((door) => door?.state === "opened" || door?.state === "locked")).toBe(true);
  });
});

describe("verdict", () => {
  it("reads the recorded gate and explains a block", () => {
    expect(verdict(load(samples.regression))).toEqual({
      tone: "blocked",
      title: "Gate blocked",
      lines: ["4 doors opened that should stay locked.", "All 4 are new since the baseline."],
    });
    expect(verdict(load(samples.vulnerable)).lines).toEqual(["4 doors opened that should stay locked."]);
  });

  it("reports a pass", () => {
    expect(verdict(load(samples.fixed))).toEqual({ tone: "passed", title: "Gate passed", lines: ["All 18 required checks passed."] });
  });

  it("follows the gate even when the checks look clean", () => {
    const report = load(samples.fixed);
    report.gate = { status: "blocked", reasons: ["comparison_policy_changed"], blocking_checks: [] };
    expect(verdict(report)).toMatchObject({ tone: "blocked", lines: ["The policy changed since the baseline, so the two runs can't be compared."] });
  });

  it("never guesses a verdict that the report didn't record", () => {
    const { gate: _gate, ...legacy } = structuredClone(samples.regression);
    expect(verdict(load(legacy))).toMatchObject({ tone: "unknown", title: "Gate verdict not recorded" });
  });
});

describe("comparison headline", () => {
  it("matches the wording the CLI writes into its HTML report", () => {
    const headline = comparisonHeadline(load(samples.regression).comparison);
    expect(headline).toBe("Compared with baseline: 4 newly failing");
    expect(regressionHtml).toContain(headline);
  });
});
