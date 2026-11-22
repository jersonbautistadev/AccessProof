import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AccessPlan } from "./components/AccessPlan";
import { DetailsPanel } from "./components/DetailsPanel";
import { LoadScreen } from "./components/LoadScreen";
import { buildPlan, comparisonHeadline, verdict } from "./model";
import { checkReport, readReportFile, type Report } from "./report";
import { SAMPLES } from "./samples";

type Source = { kind: "sample"; id: string; label: string } | { kind: "file"; name: string };
type Problem = { title: string; problems: string[] };

function readHash(): URLSearchParams {
  return new URLSearchParams(window.location.hash.slice(1));
}

function writeHash(source: Source | null, checkId: string | null) {
  const params = new URLSearchParams();
  if (source?.kind === "sample") params.set("sample", source.id);
  if (checkId) params.set("check", checkId);
  const hash = params.toString();
  window.history.replaceState(null, "", hash ? `#${hash}` : window.location.pathname + window.location.search);
}

export function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);

  const show = useCallback((next: Report, nextSource: Source, checkId: string | null = null) => {
    const known = checkId && next.results.some((result) => result.id === checkId) ? checkId : null;
    setReport(next);
    setSource(nextSource);
    setProblem(null);
    setSelectedId(known);
    setPanelOpen(Boolean(known));
    writeHash(nextSource, known);
  }, []);

  const openSample = useCallback(
    (id: string, checkId: string | null = null) => {
      const sample = SAMPLES.find((item) => item.id === id);
      if (!sample) return;
      const loaded = checkReport(sample.data);
      if (loaded.ok) show(loaded.report, { kind: "sample", id, label: sample.label }, checkId);
      else setProblem(loaded);
    },
    [show],
  );

  const openFile = useCallback(
    async (file: File) => {
      const loaded = await readReportFile(file);
      if (loaded.ok) show(loaded.report, { kind: "file", name: file.name });
      else setProblem(loaded);
    },
    [show],
  );

  // Deep links: #sample=regression&check=permission:bob-record:alice
  useEffect(() => {
    const params = readHash();
    const sample = params.get("sample");
    if (sample) openSample(sample, params.get("check"));
  }, [openSample]);

  const openDetails = useCallback(
    (checkId: string | null, from: HTMLElement | null) => {
      opener.current = from;
      setSelectedId(checkId);
      setPanelOpen(true);
      writeHash(source, checkId);
    },
    [source],
  );

  const select = useCallback(
    (checkId: string) => {
      setSelectedId(checkId);
      writeHash(source, checkId);
    },
    [source],
  );

  const closeDetails = useCallback(() => {
    setPanelOpen(false);
    writeHash(source, null);
    // Return focus to whatever opened the panel. The opener is never inside the panel,
    // so it stays focusable when the panel becomes inert.
    opener.current?.focus();
  }, [source]);

  const plan = useMemo(() => (report ? buildPlan(report) : null), [report]);

  if (!report || !plan) {
    return (
      <div className="app">
        <TopBar />
        <LoadScreen problem={problem} onFile={openFile} onSample={(id) => openSample(id)} />
      </div>
    );
  }

  const outcome = verdict(report);
  const firstBlocking = report.gate?.blocking_checks[0] ?? null;

  return (
    <div className={`app${panelOpen ? " app--panel-open" : ""}`}>
      <TopBar
        sourceLabel={source?.kind === "sample" ? `Sample: ${source.label}` : source?.name}
        onOpenAnother={() => {
          setReport(null);
          setSource(null);
          setPanelOpen(false);
          setSelectedId(null);
          writeHash(null, null);
        }}
      />
      <main className="overview">
        <div className="summary">
          <div className="summary__title">
            <h1>Who got through</h1>
            <p className="summary__sub">
              {report.suite_id}, policy {report.policy_version}. {comparisonHeadline(report.comparison)}.
            </p>
          </div>
          <div className="summary__actions">
            <div className={`verdict verdict--${outcome.tone}`} role="status">
              <p className="verdict__title">{outcome.title}</p>
              {outcome.lines.map((line) => (
                <p key={line} className="verdict__line">
                  {line}
                </p>
              ))}
            </div>
            <button
              type="button"
              className="button"
              aria-expanded={panelOpen}
              onClick={(event) => openDetails(selectedId ?? firstBlocking, event.currentTarget)}
            >
              Show details
            </button>
          </div>
        </div>

        <AccessPlan plan={plan} selectedId={panelOpen ? selectedId : null} onOpen={openDetails} />

        <footer className="meta">
          <dl className="meta__facts">
            <dt>Target</dt>
            <dd>{report.target}, GET only</dd>
            <dt>Created</dt>
            <dd>{new Date(report.created_at).toLocaleString()}</dd>
            <dt>Written by</dt>
            <dd>AccessProof {report.tool_version}</dd>
            <dt>Policy fingerprint</dt>
            <dd>
              <code title={report.policy_fingerprint}>{report.policy_fingerprint.slice(0, 12)}</code>
            </dd>
          </dl>
          <p className="meta__limitation">{report.limitation}</p>
        </footer>
      </main>

      <DetailsPanel report={report} open={panelOpen} selectedId={selectedId} onSelect={select} onClose={closeDetails} />
    </div>
  );
}

function TopBar({ sourceLabel, onOpenAnother }: { sourceLabel?: string; onOpenAnother?: () => void }) {
  return (
    <header className="topbar">
      <p className="topbar__brand">
        <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
          <rect width="32" height="32" rx="7" fill="currentColor" />
          <rect x="9" y="15" width="14" height="10" rx="2" fill="none" stroke="#F2F5F7" strokeWidth="2.4" />
          <path d="M12 15v-3a4 4 0 0 1 7.5-2" fill="none" stroke="#FF7A6B" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
        AccessProof <span className="topbar__product">report viewer</span>
      </p>
      {sourceLabel && <p className="topbar__source">{sourceLabel}</p>}
      {onOpenAnother && (
        <button type="button" className="button button--quiet" onClick={onOpenAnother}>
          Open another report
        </button>
      )}
    </header>
  );
}
