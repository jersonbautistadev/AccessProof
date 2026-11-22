import { useId, useRef, useState } from "react";
import { SAMPLES } from "../samples";

interface Props {
  problem: { title: string; problems: string[] } | null;
  onFile: (file: File) => void;
  onSample: (id: string) => void;
}

export function LoadScreen({ problem, onFile, onSample }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const errorId = useId();

  return (
    <main className="load">
      <div className="load__intro">
        <h1 className="load__title">Who got through?</h1>
        <p className="load__lede">
          Open an AccessProof report to see every permission check as a door: locked, opened, or breached by the wrong
          keycard.
        </p>
      </div>

      <div
        className={`dropzone${dragging ? " dropzone--active" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = event.dataTransfer.files[0];
          if (file) onFile(file);
        }}
      >
        <p className="dropzone__text">Drop a report.json here</p>
        <button
          type="button"
          className="button button--primary"
          aria-describedby={problem ? errorId : undefined}
          onClick={() => input.current?.click()}
        >
          Choose report.json
        </button>
        <input
          ref={input}
          type="file"
          accept=".json,application/json"
          className="visually-hidden"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = "";
          }}
        />
        <p className="dropzone__hint">
          AccessProof writes it after every run, by default to <code>reports/latest/report.json</code>.
        </p>
      </div>

      {problem && (
        <div className="load__error" role="alert" id={errorId}>
          <p className="load__error-title">{problem.title}</p>
          <ul>
            {problem.problems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      <section className="samples" aria-labelledby="samples-title">
        <h2 id="samples-title" className="samples__title">
          No report yet? Open a sample
        </h2>
        <ul className="samples__list">
          {SAMPLES.map((sample) => (
            <li key={sample.id}>
              <button type="button" className="sample" onClick={() => onSample(sample.id)}>
                <span className="sample__label">{sample.label}</span>
                <span className="sample__description">{sample.description}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <p className="load__privacy">Reports open in this browser only. Nothing is uploaded or stored.</p>
    </main>
  );
}
