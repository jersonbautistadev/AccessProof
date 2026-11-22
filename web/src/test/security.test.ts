import { describe, expect, it } from "vitest";
import vercel from "../../vercel.json";
import { CONTENT_SECURITY_POLICY, HEADER_ONLY_DIRECTIVES } from "../security";

describe("deployment security headers", () => {
  it("sends the same policy as the built page's meta tag, plus header-only directives", () => {
    const all = vercel.headers.find((rule) => rule.source === "/(.*)")?.headers ?? [];
    const csp = all.find((header) => header.key === "Content-Security-Policy")?.value;
    expect(csp).toBe(`${CONTENT_SECURITY_POLICY}; ${HEADER_ONLY_DIRECTIVES}`);
    expect(all.map((header) => header.key)).toEqual(
      expect.arrayContaining(["X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"]),
    );
  });

  it("never allows inline scripts, eval, or network access", () => {
    expect(CONTENT_SECURITY_POLICY).not.toMatch(/unsafe-inline|unsafe-eval|\*/);
    expect(CONTENT_SECURITY_POLICY).toContain("connect-src 'none'");
  });
});
