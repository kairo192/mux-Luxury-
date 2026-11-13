// The server stores times in UTC without a zone marker ("2026-11-11 10:00:00",
// SQLite CURRENT_TIMESTAMP and PostgreSQL TIMESTAMP alike). `new Date()` would
// read such a string as LOCAL time, so every time on screen would be one hour
// early in Algeria. serverDate() reads it as UTC; strings that already carry a
// zone ("…Z", "+01:00") and date-only strings are left as they are.
const NAIVE_DATETIME = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

export function serverDate(value: string | number | Date | null | undefined): Date {
  if (value instanceof Date) return value;
  if (typeof value === "number") return new Date(value);
  const s = String(value ?? "").trim();
  if (NAIVE_DATETIME.test(s)) return new Date(s.replace(" ", "T") + "Z");
  return new Date(s);
}

/** "11/11/2026 11:00" style, in the shop's local time. */
export function formatServerDateTime(value: string | null | undefined, locale = "fr-FR"): string {
  if (!value) return "—";
  const d = serverDate(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString(locale);
}

/** Local calendar date "YYYY-MM-DD" (toISOString() would give the UTC date:
 *  between midnight and 1 am in Algeria that is still "yesterday"). */
export function localDateIso(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
