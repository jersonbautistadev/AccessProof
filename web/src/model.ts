import type { Comparison, Report, Result } from "./report";

// Turns a report into the access plan: keycards (identities) across the top, rooms
// (resources) down the side, and one door per permission check. The gate verdict is
// read from report.gate and never re-derived here.

export type DoorState = "opened" | "locked" | "breached" | "refused" | "unverified" | "unchecked";
export type Change = "new" | "fixed" | null;

export interface Door {
  check: Result;
  state: DoorState;
  change: Change;
}

export interface Keycard {
  id: string;
  /** The identity verification result; absent for the anonymous identity. */
  identityCheck?: Result;
}

export interface Room {
  id: string;
  control?: Result;
  doors: Array<Door | null>;
}

export interface Plan {
  keycards: Keycard[];
  rooms: Room[];
}

export const DOOR_LABEL: Record<DoorState, string> = {
  opened: "Opened",
  locked: "Locked",
  breached: "Breached",
  refused: "Refused",
  unverified: "Unverified",
  unchecked: "Not checked",
};

export const DOOR_MEANING: Record<DoorState, string> = {
  opened: "Opened for the right keycard",
  locked: "Stayed locked, as expected",
  breached: "Opened for the wrong keycard",
  refused: "Stayed locked for a keycard that should open it",
  unverified: "Couldn't be verified",
  unchecked: "Not checked",
};

export function doorState(check: Result): DoorState {
  switch (check.status) {
    case "passed":
      return check.expected === "allow" ? "opened" : "locked";
    case "failed":
      return check.expected === "allow" ? "refused" : "breached";
    case "inconclusive":
      return "unverified";
    case "skipped":
      return "unchecked";
  }
}

export function changeOf(id: string, comparison: Comparison): Change {
  if (comparison.newly_failing.includes(id) || comparison.newly_inconclusive.includes(id)) return "new";
  if (comparison.resolved.includes(id)) return "fixed";
  return null;
}

function unique<T>(values: T[]): T[] {
  return [...new Set(values)];
}

export function buildPlan(report: Report): Plan {
  const identityChecks = new Map(
    report.results.filter((result) => result.kind === "identity").map((result) => [result.identity, result]),
  );
  const permissions = report.results.filter((result) => result.kind === "permission");
  const controls = new Map(
    report.results.filter((result) => result.kind === "control").map((result) => [result.resource ?? "", result]),
  );
  const byId = new Map(permissions.map((result) => [result.id, result]));

  // Verified identities in report order, then identities without a credential (anonymous).
  const identities = unique([...identityChecks.keys(), ...permissions.map((result) => result.identity)]);
  const keycards = identities.map((id) => ({ id, identityCheck: identityChecks.get(id) }));
  const resources = unique([...controls.keys(), ...permissions.map((result) => result.resource ?? "")]).filter(Boolean);

  const rooms = resources.map((resource) => ({
    id: resource,
    control: controls.get(resource),
    doors: keycards.map((card) => {
      const check = byId.get(`permission:${resource}:${card.id}`);
      return check ? { check, state: doorState(check), change: changeOf(check.id, report.comparison) } : null;
    }),
  }));
  return { keycards, rooms };
}

export function comparisonHeadline(comparison: Comparison): string {
  switch (comparison.status) {
    case "not_requested":
      return "No baseline comparison requested";
    case "policy_changed":
      return "Not comparable: the policy changed since the baseline";
    case "coverage_mismatch":
      return "Not comparable: the set of checks differs from the baseline";
    case "equivalent": {
      const parts = [
        [comparison.newly_failing.length, "newly failing"],
        [comparison.newly_inconclusive.length, "newly inconclusive"],
        [comparison.resolved.length, "resolved"],
      ]
        .filter(([count]) => Number(count) > 0)
        .map(([count, label]) => `${count} ${label}`);
      return `Compared with baseline: ${parts.length ? parts.join(", ") : "no changes"}`;
    }
  }
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

export interface Verdict {
  tone: "blocked" | "passed" | "unknown";
  title: string;
  lines: string[];
}

export function verdict(report: Report): Verdict {
  const gate = report.gate;
  if (!gate) {
    return {
      tone: "unknown",
      title: "Gate verdict not recorded",
      lines: ["This report predates recorded verdicts. Run it again with a current AccessProof to see whether it blocks CI."],
    };
  }
  if (gate.status === "passed") {
    const required = report.results.filter((result) => result.required).length;
    return { tone: "passed", title: "Gate passed", lines: [`All ${required} required checks passed.`] };
  }

  const byId = new Map(report.results.map((result) => [result.id, result]));
  const blocking = gate.blocking_checks.map((id) => byId.get(id)).filter((result) => result !== undefined);
  const count = (predicate: (result: Result) => boolean) => blocking.filter(predicate).length;
  const breached = count((r) => r.status === "failed" && r.expected !== "allow");
  const refused = count((r) => r.status === "failed" && r.expected === "allow");
  const unverified = count((r) => r.status === "inconclusive");
  const notRun = count((r) => r.status === "skipped");

  const lines: string[] = [];
  if (breached) lines.push(`${plural(breached, "door", "doors")} opened that should stay locked.`);
  if (refused) lines.push(`${plural(refused, "door", "doors")} stayed locked for a keycard that should open it.`);
  if (unverified) lines.push(`${plural(unverified, "check", "checks")} couldn't be verified.`);
  if (notRun) lines.push(`${plural(notRun, "required check was", "required checks were")} not run.`);
  if (gate.reasons.includes("comparison_policy_changed")) {
    lines.push("The policy changed since the baseline, so the two runs can't be compared.");
  }
  if (gate.reasons.includes("comparison_coverage_mismatch")) {
    lines.push("The baseline has a different set of checks, so the two runs can't be compared.");
  }

  const changed = new Set([...report.comparison.newly_failing, ...report.comparison.newly_inconclusive]);
  const isNew = blocking.filter((result) => changed.has(result.id)).length;
  if (isNew && isNew === blocking.length) lines.push(isNew === 1 ? "It's new since the baseline." : `All ${isNew} are new since the baseline.`);
  else if (isNew) lines.push(`${isNew} of them ${isNew === 1 ? "is" : "are"} new since the baseline.`);

  return { tone: "blocked", title: "Gate blocked", lines };
}
