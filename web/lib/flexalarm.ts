/** Flex-Alarm types mirroring the /flexalarm endpoints in main.py. */

export interface Alert {
  id: number;
  household_id: string;
  dedup_key: string;
  kind: string;
  title: string;
  body: string;
  status: string;
  channel: string | null;
  reason: string;
  created_at: string;
}

export interface AlertsResponse {
  household_id: string;
  alerts: Alert[];
}

export interface WatchReport {
  household_id: string;
  day: string;
  candidates: number;
  fired: number;
  held: number;
  delivered: number;
  released: number;
  skipped: number;
  duplicates: number;
  errors: string[];
}

function parseAlert(value: unknown): Alert {
  if (typeof value !== "object" || value === null) {
    throw new Error("Alert must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.id !== "number" ||
    typeof record.household_id !== "string" ||
    typeof record.dedup_key !== "string" ||
    typeof record.kind !== "string" ||
    typeof record.title !== "string" ||
    typeof record.body !== "string" ||
    typeof record.status !== "string" ||
    (record.channel !== null && typeof record.channel !== "string") ||
    typeof record.reason !== "string" ||
    typeof record.created_at !== "string"
  ) {
    throw new Error("Alert has invalid fields");
  }
  return {
    id: record.id,
    household_id: record.household_id,
    dedup_key: record.dedup_key,
    kind: record.kind,
    title: record.title,
    body: record.body,
    status: record.status,
    channel: record.channel,
    reason: record.reason,
    created_at: record.created_at,
  };
}

export function parseAlertsResponse(value: unknown): AlertsResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("AlertsResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (typeof record.household_id !== "string" || !Array.isArray(record.alerts)) {
    throw new Error("AlertsResponse has invalid fields");
  }
  return {
    household_id: record.household_id,
    alerts: record.alerts.map(parseAlert),
  };
}

export function parseWatchReport(value: unknown): WatchReport {
  if (typeof value !== "object" || value === null) {
    throw new Error("WatchReport must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    typeof record.day !== "string" ||
    typeof record.candidates !== "number" ||
    typeof record.fired !== "number" ||
    typeof record.held !== "number" ||
    typeof record.delivered !== "number" ||
    typeof record.released !== "number" ||
    typeof record.skipped !== "number" ||
    typeof record.duplicates !== "number" ||
    !Array.isArray(record.errors)
  ) {
    throw new Error("WatchReport has invalid fields");
  }
  return {
    household_id: record.household_id,
    day: record.day,
    candidates: record.candidates,
    fired: record.fired,
    held: record.held,
    delivered: record.delivered,
    released: record.released,
    skipped: record.skipped,
    duplicates: record.duplicates,
    errors: record.errors.map(String),
  };
}
