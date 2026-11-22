/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// The viewer renders untrusted report files, so the built page allows only its own
// scripts, styles, and fonts, and cannot make network requests or submit forms.
// Applied to production builds only: the dev server needs inline scripts for HMR.
const CONTENT_SECURITY_POLICY = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self'",
  "font-src 'self'",
  "img-src 'self'",
  "connect-src 'none'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

function contentSecurityPolicy(): Plugin {
  return {
    name: "accessproof-content-security-policy",
    apply: "build",
    transformIndexHtml(html) {
      // After the charset declaration, which must stay first in <head>.
      const charset = '<meta charset="UTF-8" />';
      if (!html.includes(charset)) throw new Error("index.html must declare <meta charset=\"UTF-8\" />");
      return html.replace(
        charset,
        `${charset}\n    <meta http-equiv="Content-Security-Policy" content="${CONTENT_SECURITY_POLICY}" />`,
      );
    },
  };
}

export default defineConfig({
  // Relative asset paths, so the build works from any subpath (for example GitHub Pages).
  base: "./",
  plugins: [react(), contentSecurityPolicy()],
  // Sample reports and the schema live outside web/.
  server: { fs: { allow: [".."] } },
  build: { target: "es2022", assetsInlineLimit: 0, sourcemap: false },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], css: false },
});
