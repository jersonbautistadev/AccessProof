// The published sample reports from docs/samples, bundled so the viewer can be tried
// without running AccessProof. They go through the same schema check as any file.
import fixed from "../../docs/samples/fixed.json";
import regression from "../../docs/samples/regression.json";
import vulnerable from "../../docs/samples/vulnerable.json";

export interface Sample {
  id: string;
  label: string;
  description: string;
  data: unknown;
}

export const SAMPLES: Sample[] = [
  {
    id: "vulnerable",
    label: "Vulnerable app",
    description: "Ownership and admin-role checks are missing. Four doors open for the wrong keycard.",
    data: vulnerable,
  },
  {
    id: "fixed",
    label: "Fixed app",
    description: "Both checks restored. Every door behaves, and the four failures are resolved.",
    data: fixed,
  },
  {
    id: "regression",
    label: "Regression",
    description: "The bugs come back, compared with the fixed run as the baseline.",
    data: regression,
  },
];
