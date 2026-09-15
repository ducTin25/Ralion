/**
 * Backend returns naive UTC datetimes without an offset. Browsers otherwise parse those values
 * as local time, so add the UTC designator when the server did not include timezone information.
 */
export function parseServerUtc(value: string): Date {
  return new Date(/([Zz]|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`);
}

export function formatServerDateTime(value: string | null, locale = "en-GB"): string {
  if (!value) return "—";
  const parsed = parseServerUtc(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}
