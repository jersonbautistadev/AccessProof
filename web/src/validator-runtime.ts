// ES-module replacements for the three Ajv runtime helpers that Ajv's standalone
// output pulls in with CommonJS `require`. scripts/build-validator.mjs rewrites the
// generated validator to import these instead, so the bundle stays plain ESM.

/** Deep equality for JSON values (Ajv `uniqueItems`). */
export function jsonEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) {
    return Number.isNaN(a) && Number.isNaN(b);
  }
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((item, index) => jsonEqual(item, b[index]));
  }
  const left = a as Record<string, unknown>;
  const right = b as Record<string, unknown>;
  const keys = Object.keys(left);
  return (
    keys.length === Object.keys(right).length &&
    keys.every((key) => Object.prototype.hasOwnProperty.call(right, key) && jsonEqual(left[key], right[key]))
  );
}

/** String length in Unicode code points, as JSON Schema `maxLength` defines it. */
export function codePointLength(value: string): number {
  let length = 0;
  for (const _ of value) length += 1;
  return length;
}

const DATE = /^(\d\d\d\d)-(\d\d)-(\d\d)$/;
const TIME = /^(\d\d):(\d\d):(\d\d(?:\.\d+)?)(z|([+-])(\d\d)(?::?(\d\d))?)$/i;
const DAYS = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function validDate(value: string): boolean {
  const match = DATE.exec(value);
  if (!match) return false;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const maxDay = month === 2 && isLeapYear(year) ? 29 : DAYS[month];
  return month >= 1 && month <= 12 && day >= 1 && maxDay !== undefined && day <= maxDay;
}

function validTime(value: string): boolean {
  // RFC 3339 requires a time-zone offset on date-time values.
  const match = TIME.exec(value);
  if (!match) return false;
  const [hour, minute, second] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const [offsetHour, offsetMinute] = [Number(match[6] ?? 0), Number(match[7] ?? 0)];
  if (offsetHour > 23 || offsetMinute > 59) return false;
  return hour <= 23 && minute <= 59 && second < 61;
}

/** RFC 3339 `date-time`, in the `{ validate }` shape Ajv's generated code calls. */
export const dateTimeFormat = {
  validate(value: string): boolean {
    const parts = value.split(/t|\s/i);
    return parts.length === 2 && validDate(parts[0] ?? "") && validTime(parts[1] ?? "");
  },
};
