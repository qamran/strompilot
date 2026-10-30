/** Report types mirroring the /report endpoints in main.py. */

export interface CheapWindow {
  start: string;
  end: string;
  avg_ct_kwh: number;
}

export interface ReportDay {
  day: string;
  kwh: number;
  cost_eur: number;
  cheapest_window: CheapWindow | null;
  sample: boolean;
}

export interface WorstHour {
  day: string;
  hour: number;
  price_ct_kwh: number;
}

export interface MonthlyReport {
  month: string;
  annual_kwh: number;
  days: ReportDay[];
  total_kwh: number;
  total_cost_eur: number;
  savings_eur: number;
  flat_ct_kwh: number;
  worst_hour: WorstHour | null;
  sample_days: number;
  assumptions: string[];
}

export interface MonthlyReportResponse {
  report: MonthlyReport;
  illustration_data_url: string | null;
}

export interface IllustrationResponse {
  month: string;
  illustration_data_url: string;
  cached: boolean;
}

function asRecord(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    throw new Error(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function parseWindow(value: unknown): CheapWindow {
  const record = asRecord(value, "CheapWindow");
  if (
    typeof record.start !== "string" ||
    typeof record.end !== "string" ||
    typeof record.avg_ct_kwh !== "number"
  ) {
    throw new Error("CheapWindow has invalid fields");
  }
  return {
    start: record.start,
    end: record.end,
    avg_ct_kwh: record.avg_ct_kwh,
  };
}

function parseDay(value: unknown): ReportDay {
  const record = asRecord(value, "ReportDay");
  if (
    typeof record.day !== "string" ||
    typeof record.kwh !== "number" ||
    typeof record.cost_eur !== "number" ||
    (record.cheapest_window !== null &&
      typeof record.cheapest_window !== "object") ||
    typeof record.sample !== "boolean"
  ) {
    throw new Error("ReportDay has invalid fields");
  }
  return {
    day: record.day,
    kwh: record.kwh,
    cost_eur: record.cost_eur,
    cheapest_window:
      record.cheapest_window === null
        ? null
        : parseWindow(record.cheapest_window),
    sample: record.sample,
  };
}

function parseWorst(value: unknown): WorstHour {
  const record = asRecord(value, "WorstHour");
  if (
    typeof record.day !== "string" ||
    typeof record.hour !== "number" ||
    typeof record.price_ct_kwh !== "number"
  ) {
    throw new Error("WorstHour has invalid fields");
  }
  return {
    day: record.day,
    hour: record.hour,
    price_ct_kwh: record.price_ct_kwh,
  };
}

function parseReport(value: unknown): MonthlyReport {
  const record = asRecord(value, "MonthlyReport");
  if (
    typeof record.month !== "string" ||
    typeof record.annual_kwh !== "number" ||
    !Array.isArray(record.days) ||
    typeof record.total_kwh !== "number" ||
    typeof record.total_cost_eur !== "number" ||
    typeof record.savings_eur !== "number" ||
    typeof record.flat_ct_kwh !== "number" ||
    (record.worst_hour !== null && typeof record.worst_hour !== "object") ||
    typeof record.sample_days !== "number" ||
    !Array.isArray(record.assumptions)
  ) {
    throw new Error("MonthlyReport has invalid fields");
  }
  return {
    month: record.month,
    annual_kwh: record.annual_kwh,
    days: (record.days as unknown[]).map(parseDay),
    total_kwh: record.total_kwh,
    total_cost_eur: record.total_cost_eur,
    savings_eur: record.savings_eur,
    flat_ct_kwh: record.flat_ct_kwh,
    worst_hour:
      record.worst_hour === null ? null : parseWorst(record.worst_hour),
    sample_days: record.sample_days,
    assumptions: (record.assumptions as unknown[]).map(String),
  };
}

export function parseMonthlyReportResponse(value: unknown): MonthlyReportResponse {
  const record = asRecord(value, "MonthlyReportResponse");
  if (
    typeof record.report !== "object" ||
    (record.illustration_data_url !== null &&
      typeof record.illustration_data_url !== "string")
  ) {
    throw new Error("MonthlyReportResponse has invalid fields");
  }
  return {
    report: parseReport(record.report),
    illustration_data_url: record.illustration_data_url as string | null,
  };
}

export function parseIllustrationResponse(value: unknown): IllustrationResponse {
  const record = asRecord(value, "IllustrationResponse");
  if (
    typeof record.month !== "string" ||
    typeof record.illustration_data_url !== "string" ||
    typeof record.cached !== "boolean"
  ) {
    throw new Error("IllustrationResponse has invalid fields");
  }
  return {
    month: record.month,
    illustration_data_url: record.illustration_data_url,
    cached: record.cached,
  };
}
