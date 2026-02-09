/**
 * Parse report_date from API: either YYYY-MM-DD or YYYY-MM-DD_HH-MM-SS (run id).
 * Returns a Date for display, or null if invalid.
 * Run-id format uses dashes in the time part, which JS Date doesn't accept, so we parse only the date part.
 */
export function parseReportDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  try {
    const datePart = dateStr.includes("_") ? dateStr.slice(0, dateStr.indexOf("_")) : dateStr;
    const d = new Date(datePart);
    return isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}
