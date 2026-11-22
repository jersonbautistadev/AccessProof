import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import type { Report } from "../report";
import { reportFile, samples } from "./fixtures";

function fileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("file input not found");
  return input;
}

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(() => window.history.replaceState(null, "", "/"));

describe("report viewer", () => {
  it("opens a sample, shows the recorded verdict, and drills into a breached door", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /^Regression/ }));

    const verdict = screen.getByRole("status");
    expect(verdict).toHaveTextContent("Gate blocked");
    expect(verdict).toHaveTextContent("4 doors opened that should stay locked.");

    const door = screen.getByRole("button", { name: /^bob-record, alice: Opened for the wrong keycard, new since baseline/ });
    await user.click(door);

    const panel = screen.getByRole("complementary", { name: "Failure details" });
    expect(panel).not.toHaveAttribute("inert");
    expect(within(panel).getByRole("heading", { name: "permission:bob-record:alice" })).toBeInTheDocument();
    expect(panel).toHaveTextContent("200, 82 bytes, JSON object");
    expect(panel).toHaveTextContent("/private_note");
    expect(panel).toHaveTextContent("New failure");
    expect(window.location.hash).toBe("#sample=regression&check=permission%3Abob-record%3Aalice");

    await user.keyboard("{Escape}");
    expect(panel).toHaveAttribute("inert");
    expect(door).toHaveFocus();
    expect(window.location.hash).toBe("#sample=regression");
  });

  it("filters the check list in the details panel", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /^Regression/ }));
    await user.click(screen.getByRole("button", { name: "Show details" }));

    const list = screen.getByRole("list", { name: "Checks" });
    expect(within(list).getAllByRole("button")).toHaveLength(18);
    await user.click(screen.getByRole("button", { name: /^Failed 4/ }));
    expect(within(list).getAllByRole("button")).toHaveLength(4);
    await user.type(screen.getByRole("searchbox", { name: "Filter checks by ID" }), "admin-audit");
    expect(within(list).getAllByRole("button")).toHaveLength(2);
  });

  it("restores a deep link to a sample and check", () => {
    window.history.replaceState(null, "", "/#sample=regression&check=permission%3Aadmin-audit%3Abob");
    render(<App />);
    const panel = screen.getByRole("complementary", { name: "Failure details" });
    expect(within(panel).getByRole("heading", { name: "permission:admin-audit:bob" })).toBeInTheDocument();
  });

  it("opens a report file chosen by the user", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await user.upload(fileInput(container), reportFile(samples.fixed, "after.json"));
    expect(screen.getByRole("status")).toHaveTextContent("Gate passed");
    expect(screen.getByText("after.json")).toBeInTheDocument();
  });

  it("explains why a file was refused", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    const bad = structuredClone(samples.fixed) as Record<string, unknown>;
    bad.response_body = "{}";
    await user.upload(fileInput(container), reportFile(bad));
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("This file isn't a valid AccessProof report.");
    expect(alert).toHaveTextContent('unexpected field "response_body"');

    await user.upload(fileInput(container), reportFile("{not json"));
    expect(screen.getByRole("alert")).toHaveTextContent("This file isn't valid JSON.");
  });

  it("renders report text as text, never as markup", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    const hostile = structuredClone(samples.fixed) as unknown as Report;
    const target = hostile.results.find((result) => result.id === "permission:bob-record:alice");
    if (!target) throw new Error("fixture changed");
    Object.assign(target, {
      status: "skipped",
      reason: "explicit_skip",
      expected: "unspecified",
      evidence: { skip_reason: '<img src=x onerror="window.__xss=1">' },
    });
    hostile.gate = { status: "blocked", reasons: ["required_checks_not_passed"], blocking_checks: [target.id] };
    await user.upload(fileInput(container), reportFile(hostile));

    await user.click(screen.getByRole("button", { name: /^bob-record, alice: Not checked/ }));
    expect(screen.getByText('<img src=x onerror="window.__xss=1">')).toBeInTheDocument();
    expect(container.ownerDocument.querySelector("img")).toBeNull();
    expect((window as unknown as { __xss?: number }).__xss).toBeUndefined();
  });

  it("says when a report has no recorded verdict", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    const { gate: _gate, ...legacy } = structuredClone(samples.regression);
    await user.upload(fileInput(container), reportFile(legacy));
    expect(screen.getByRole("status")).toHaveTextContent("Gate verdict not recorded");
  });
});
