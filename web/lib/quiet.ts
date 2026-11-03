/** Quiet-hours parsing shared by the plan timeline. */

export interface QuietRange {
  start: string;
  end: string;
}

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

export function parseQuietRange(value: unknown): QuietRange | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  const { start, end } = record;
  if (
    typeof start !== "string" ||
    typeof end !== "string" ||
    !TIME.test(start) ||
    !TIME.test(end) ||
    start === end
  ) {
    return null;
  }
  return { start, end };
}
