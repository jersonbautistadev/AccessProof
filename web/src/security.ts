// Single source of the viewer's Content Security Policy. vite.config.ts puts it in a
// <meta> tag for any static host; vercel.json sends it as an HTTP header, which can also
// forbid framing. A test keeps the two in sync.
export const CONTENT_SECURITY_POLICY = [
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

/** Only enforceable as an HTTP header, not in a <meta> policy. */
export const HEADER_ONLY_DIRECTIVES = "frame-ancestors 'none'";
