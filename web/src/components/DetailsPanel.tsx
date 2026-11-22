import { useEffect, useMemo, useRef, useState } from "react";
import { changeOf, comparisonHeadline } from "../model";
import { describeReason } from "../reasons";
import type { AssertionCheck, Report, Result, Status } from "../report";
import { StatusMark } from "./icons";

interface Props {
  report: Report;
  open: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
}

const FILTERS: Array<{ id: Status | "all"; label: string }> = [
  { id: "all", label: "All" },
  { id: "failed", label: "Failed" },
  { id: "inconclusive", label: "Inconclusive" },
  { id: "skipped", label: "Skipped" },
  { id: "passed", label: "Passed" },
];

export function DetailsPanel({ report, open, selectedId, onSelect, onClose }: Props) {
  const heading = useRef<HTMLHeadingElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Status | "all">("all");
  const selected = report.results.find((result) => result.id === selectedId) ?? null;

  useEffect(() => {
    if (open) heading.current?.focus();
  }, [open, selectedId]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "/" && !(event.target instanceof HTMLInputElement)) {
        event.preventDefault();
        search.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: report.results.length };
    for (const check of report.results) result[check.status] = (result[check.status] ?? 0) + 1;
    return result;
  }, [report]);

  const visible = report.results.filter(
    (check) => (filter === "all" || check.status === filter) && check.id.toLowerCase().includes(query.trim().toLowerCase()),
  );

  return (
    <aside className={`panel${open ? " panel--open" : ""}`} aria-labelledby="panel-title" inert={!open}>
      <div className="panel__header">
        <h2 id="panel-title" className="panel__title" tabIndex={-1} ref={heading}>
          {selected ? (selected.status === "failed" ? "Failure details" : "Check details") : "Report details"}
        </h2>
        <button type="button" className="panel__close" onClick={onClose}>
          Close <kbd>Esc</kbd>
        </button>
      </div>

      <div className="panel__body">
        {selected && <CheckDetail check={selected} report={report} />}

        <section aria-labelledby="baseline-title">
          <h3 id="baseline-title" className="panel__label">
            Since baseline
          </h3>
          <BaselineDiff report={report} selectedId={selectedId} onSelect={onSelect} />
        </section>

        <section aria-labelledby="checks-title">
          <h3 id="checks-title" className="panel__label">
            All checks
          </h3>
          <div className="filter">
            <input
              ref={search}
              type="search"
              className="filter__search"
              placeholder="Filter by check ID"
              aria-label="Filter checks by ID"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <span className="filter__hint" aria-hidden="true">
              <kbd>/</kbd> to search
            </span>
          </div>
          <div className="chips" role="group" aria-label="Show checks with status">
            {FILTERS.map((option) => (
              <button
                key={option.id}
                type="button"
                className="chip"
                aria-pressed={filter === option.id}
                onClick={() => setFilter(option.id)}
              >
                {option.label} <span className="chip__count">{counts[option.id] ?? 0}</span>
              </button>
            ))}
          </div>
          <ul className="checks" aria-label="Checks">
            {visible.map((check) => (
              <li key={check.id}>
                <button
                  type="button"
                  className={`checks__row checks__row--${check.status}`}
                  aria-current={check.id === selectedId ? "true" : undefined}
                  onClick={() => onSelect(check.id)}
                >
                  <span className="checks__status">
                    <StatusMark status={check.status} />
                    {check.status}
                  </span>
                  <code className="checks__id">{check.id}</code>
                </button>
              </li>
            ))}
            {visible.length === 0 && <li className="checks__empty">No checks match this filter.</li>}
          </ul>
        </section>
      </div>
    </aside>
  );
}

function BaselineDiff({ report, selectedId, onSelect }: { report: Report; selectedId: string | null; onSelect: (id: string) => void }) {
  const comparison = report.comparison;
  if (comparison.status === "not_requested") {
    return <p className="panel__note">No baseline was compared. Run AccessProof with --baseline to see what changed.</p>;
  }
  const lines: Array<{ id: string; sign: string; word: string; tone: string }> = [
    ...comparison.newly_failing.map((id) => ({ id, sign: "+", word: "failed", tone: "fail" })),
    ...comparison.newly_inconclusive.map((id) => ({ id, sign: "+", word: "inconclusive", tone: "warn" })),
    ...comparison.resolved.map((id) => ({ id, sign: "-", word: "fixed", tone: "pass" })),
    ...comparison.added.map((id) => ({ id, sign: "+", word: "added", tone: "neutral" })),
    ...comparison.removed.map((id) => ({ id, sign: "-", word: "removed", tone: "neutral" })),
  ];
  const known = new Set(report.results.map((result) => result.id));
  const unchanged = report.results.length - new Set(lines.map((line) => line.id)).size;
  return (
    <>
      <p className="panel__note">{comparisonHeadline(comparison)}</p>
      {lines.length > 0 && (
        <ul className="diff" aria-label="Changes since baseline">
          {lines.map((line) => (
            <li key={`${line.word}:${line.id}`}>
              {known.has(line.id) ? (
                <button
                  type="button"
                  className={`diff__line diff__line--${line.tone}`}
                  aria-current={line.id === selectedId ? "true" : undefined}
                  onClick={() => onSelect(line.id)}
                >
                  {line.sign} {line.word.padEnd(12, " ")} {line.id}
                </button>
              ) : (
                <span className={`diff__line diff__line--${line.tone}`}>
                  {line.sign} {line.word.padEnd(12, " ")} {line.id}
                </span>
              )}
            </li>
          ))}
          {comparison.status === "equivalent" && unchanged > 0 && (
            <li className="diff__line diff__line--context">{`  ${unchanged} checks unchanged`}</li>
          )}
        </ul>
      )}
    </>
  );
}

function AssertionList({ title, checks }: { title: string; checks?: AssertionCheck[] }) {
  if (!checks?.length) return null;
  return (
    <>
      <dt>{title}</dt>
      <dd>
        <ul className="assertions">
          {checks.map((check, index) => (
            <li key={`${check.kind}:${check.pointer ?? index}`} className={check.matched ? "is-match" : "is-miss"}>
              <code>{check.kind === "status" ? "status" : check.pointer}</code> {check.matched ? "matched" : "did not match"}
            </li>
          ))}
        </ul>
      </dd>
    </>
  );
}

function CheckDetail({ check, report }: { check: Result; report: Report }) {
  const evidence = check.evidence;
  const change = changeOf(check.id, report.comparison);
  const since =
    report.comparison.status === "not_requested"
      ? "Not compared"
      : change === "new"
        ? check.status === "failed"
          ? "New failure"
          : "Newly inconclusive"
        : change === "fixed"
          ? "Fixed"
          : "Unchanged";
  const response =
    evidence.http_status === undefined && evidence.body_bytes === undefined
      ? "No request was made"
      : evidence.http_status === null
        ? "No response"
        : `${evidence.http_status}, ${evidence.body_bytes ?? 0} bytes${evidence.json_object ? ", JSON object" : ""}`;

  return (
    <section className="detail" aria-labelledby="detail-title">
      <h3 id="detail-title" className="detail__id">
        <code>{check.id}</code>
      </h3>
      <p className={`detail__result detail__result--${check.status}`}>
        <StatusMark status={check.status} /> {check.status}
        <span className="detail__reason">{describeReason(check.reason)}</span>
      </p>
      <dl className="detail__facts">
        <dt>Expected</dt>
        <dd>{check.expected}</dd>
        <dt>Gate</dt>
        <dd>{check.required ? "Required" : "Optional, cannot block"}</dd>
        <dt>Since baseline</dt>
        <dd className={change === "new" ? "is-new" : undefined}>{since}</dd>
        <dt>Response</dt>
        <dd>{response}</dd>
        {evidence.transport_error && (
          <>
            <dt>Transport</dt>
            <dd>
              <code>{evidence.transport_error}</code>
            </dd>
          </>
        )}
        {evidence.protected_fields_present !== undefined && (
          <>
            <dt>Protected fields</dt>
            <dd>
              {evidence.protected_fields_present.length
                ? evidence.protected_fields_present.map((pointer) => (
                    <code key={pointer} className="detail__pointer">
                      {pointer}
                    </code>
                  ))
                : "None in the response"}
            </dd>
          </>
        )}
        <AssertionList title="Identity contract" checks={evidence.identity_assertions} />
        <AssertionList title="Allow contract" checks={evidence.allow_assertions} />
        <AssertionList title="Deny contract" checks={evidence.deny_assertions} />
        {evidence.control_diagnostic && (
          <>
            <dt>Control diagnostic</dt>
            <dd>{describeReason(evidence.control_diagnostic)}</dd>
          </>
        )}
        {evidence.skip_reason && (
          <>
            <dt>Skip reason</dt>
            <dd>{evidence.skip_reason}</dd>
          </>
        )}
      </dl>
    </section>
  );
}
