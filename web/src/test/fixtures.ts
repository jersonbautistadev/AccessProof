import fixed from "../../../docs/samples/fixed.json";
import regression from "../../../docs/samples/regression.json";
import vulnerable from "../../../docs/samples/vulnerable.json";
import { checkReport, type Report } from "../report";

export function load(data: unknown): Report {
  const result = checkReport(structuredClone(data));
  if (!result.ok) throw new Error(`${result.title} ${result.problems.join(" ")}`);
  return result.report;
}

export const samples = { fixed, regression, vulnerable };

export function reportFile(data: unknown, name = "report.json"): File {
  return new File([typeof data === "string" ? data : JSON.stringify(data)], name, { type: "application/json" });
}
