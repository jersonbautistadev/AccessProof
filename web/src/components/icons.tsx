import type { DoorState } from "../model";

// Door glyphs. Each is decorative (aria-hidden); the door's text label carries meaning.
const paths: Record<DoorState, React.ReactNode> = {
  opened: (
    <>
      <path d="M5 16V3h8v13" />
      <circle cx="11" cy="10" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  locked: (
    <>
      <rect x="3.5" y="8" width="11" height="8" rx="1.5" />
      <path d="M6 8V6a3 3 0 0 1 6 0v2" />
    </>
  ),
  breached: (
    <>
      <rect x="3.5" y="8" width="11" height="8" rx="1.5" />
      <path d="M6 8V6a3 3 0 0 1 5.6-1.5" />
    </>
  ),
  refused: (
    <>
      <path d="M5 16V3h8v13" />
      <path d="M3 9.5h12" />
    </>
  ),
  unverified: (
    <>
      <circle cx="9" cy="9" r="6.5" />
      <path d="M7 7.2a2 2 0 1 1 2.6 1.9c-.4.2-.6.5-.6.9v.6" />
      <circle cx="9" cy="12.6" r=".6" fill="currentColor" stroke="none" />
    </>
  ),
  unchecked: (
    <>
      <circle cx="9" cy="9" r="6.5" />
      <path d="M6 9h6" />
    </>
  ),
};

export function DoorIcon({ state, size = 22 }: { state: DoorState; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[state]}
    </svg>
  );
}

export function StatusMark({ status }: { status: "passed" | "failed" | "inconclusive" | "skipped" }) {
  const shape = {
    passed: <path d="M2 6.5l2.8 2.8L10 3.5" />,
    failed: <path d="M2.5 2.5l7 7m0-7l-7 7" />,
    inconclusive: <path d="M6 2.5v4.5M6 9.2v.3" />,
    skipped: <path d="M2.5 6h7" />,
  }[status];
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
      {shape}
    </svg>
  );
}
