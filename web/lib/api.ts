/** Typed fetch client for the Strompilot backend. */

import { parseHealthResponse, type HealthResponse } from "./contract";
import { parseAlertsResponse, parseWatchReport } from "./flexalarm";
import type { Alert, WatchReport } from "./flexalarm";
import {
  parseConfirmResponse,
  parseReadingsResponse,
  type ConfirmResponse,
  type MeterReading,
} from "./meter";
import { parsePlanCreated, parsePlanDetail } from "./plan";
import type { PlanCreated, PlanDetail } from "./plan";
import {
  parseDayAheadPriceSeries,
  type DayAheadPriceSeries,
} from "./prices";
import {
  parseIllustrationResponse,
  parseMonthlyReportResponse,
  type IllustrationResponse,
  type MonthlyReportResponse,
} from "./report";
import { parseWallboxStatus, type WallboxStatus } from "./wallbox";
import { parseApprovalStatus, type ApprovalStatus } from "./approvals";
import {
  parseEpisodesList,
  parsePreferencesMap,
  type EpisodesList,
  type PreferencesMap,
} from "./memory";
import {
  parseFeedbackListResponse,
  parseFeedbackResponse,
  type FeedbackListResponse,
  type FeedbackResponse,
} from "./feedback";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const HOUSEHOLD_ID = "demo-haushalt";

async function request<T>(
  path: string,
  parse: (value: unknown) => T,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail.slice(0, 200)}`);
  }
  return parse(await res.json());
}

function household(query = ""): string {
  const sep = query.includes("?") ? "&" : "?";
  return `${query}${sep}household_id=${encodeURIComponent(HOUSEHOLD_ID)}`;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request("/health", parseHealthResponse);
}

export function fetchPrices(day?: string): Promise<DayAheadPriceSeries> {
  const query = day ? `?date=${encodeURIComponent(day)}` : "";
  return request(`/prices/day-ahead${query}`, parseDayAheadPriceSeries);
}

export function startPlan(text: string, planDay?: string): Promise<PlanCreated> {
  return request(
    "/plan",
    parsePlanCreated,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        household_id: HOUSEHOLD_ID,
        text,
        plan_day: planDay ?? null,
      }),
    },
  );
}

export function fetchPlan(threadId: string): Promise<PlanDetail> {
  return request(`/plan/${encodeURIComponent(threadId)}`, parsePlanDetail);
}

export function traceUrl(threadId: string): string {
  return `${API_URL}/plan/${encodeURIComponent(threadId)}/trace`;
}

export function fetchApproval(threadId: string): Promise<ApprovalStatus> {
  return request(
    `/approvals/threads/${encodeURIComponent(threadId)}`,
    parseApprovalStatus,
  );
}

export function decideApproval(
  threadId: string,
  approved: boolean,
): Promise<ApprovalStatus> {
  return request(
    `/approvals/threads/${encodeURIComponent(threadId)}/decide`,
    parseApprovalStatus,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    },
  );
}

export function fetchAlerts(): Promise<Alert[]> {
  return request(household("/flexalarm/alerts"), (value) => {
    const parsed = parseAlertsResponse(value);
    if (parsed.household_id !== HOUSEHOLD_ID) {
      throw new Error("Alert household mismatch");
    }
    return parsed.alerts;
  });
}

export function triggerWatch(): Promise<WatchReport> {
  return request(household("/flexalarm/watch"), parseWatchReport, {
    method: "POST",
  });
}

export async function uploadMeterPhoto(
  file: File,
  keepPhoto: boolean,
): Promise<MeterReading> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${API_URL}${household("/meter/readings")}&keep_photo=${keepPhoto}`,
    { method: "POST", body: form },
  );
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
  const parsed = parseReadingsResponse({
    household_id: HOUSEHOLD_ID,
    readings: [await res.json()],
  });
  return parsed.readings[0];
}

export function fetchReadings(): Promise<MeterReading[]> {
  return request(household("/meter/readings"), (value) => {
    return parseReadingsResponse(value).readings;
  });
}

export function confirmReading(
  readingId: number,
  correctedValueKwh?: number,
): Promise<ConfirmResponse> {
  return request(
    household(`/meter/readings/${readingId}/confirm`),
    parseConfirmResponse,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        corrected_value_kwh: correctedValueKwh ?? null,
      }),
    },
  );
}

export type FeedbackVerdict = "too_early" | "too_late" | "good";

export function submitFeedback(
  device: string,
  verdict: FeedbackVerdict,
  note = "",
): Promise<FeedbackResponse> {
  return request(household("/feedback"), parseFeedbackResponse, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device, verdict, note }),
  });
}

export function fetchFeedback(): Promise<FeedbackListResponse> {
  return request(household("/feedback"), parseFeedbackListResponse);
}

export function fetchPreferences(): Promise<PreferencesMap> {
  return request(household("/memory/preferences"), parsePreferencesMap);
}

export async function forgetPreference(key: string): Promise<void> {
  const res = await fetch(
    `${API_URL}${household(`/memory/preferences/${encodeURIComponent(key)}`)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
}

export function fetchHistory(): Promise<EpisodesList> {
  return request(household("/memory/history"), parseEpisodesList);
}

export function fetchMonthlyReport(month: string): Promise<MonthlyReportResponse> {
  return request(
    household(`/report/monthly?month=${encodeURIComponent(month)}`),
    parseMonthlyReportResponse,
  );
}

export function generateIllustration(month: string): Promise<IllustrationResponse> {
  return request(
    household(`/report/monthly/illustration?month=${encodeURIComponent(month)}`),
    parseIllustrationResponse,
    { method: "POST" },
  );
}

export function fetchWallbox(): Promise<WallboxStatus> {
  return request("/wallbox/status", parseWallboxStatus);
}

export function programWallbox(
  start: string,
  end: string,
  maxKw: number,
): Promise<WallboxStatus> {
  return request("/wallbox/program", parseWallboxStatus, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start, end, max_kw: maxKw }),
  });
}
