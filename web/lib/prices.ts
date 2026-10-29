/** Day-ahead price types mirroring api/strompilot/prices/models.py. */

export interface DayAheadPricePoint {
  start: string;
  end: string;
  eur_per_mwh: number;
}

export interface DayAheadPriceSeries {
  date: string;
  source: string;
  stale: boolean;
  unit: string;
  attribution: string;
  prices: DayAheadPricePoint[];
}

function parsePoint(value: unknown): DayAheadPricePoint {
  if (typeof value !== "object" || value === null) {
    throw new Error("DayAheadPricePoint must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.start !== "string" ||
    typeof record.end !== "string" ||
    typeof record.eur_per_mwh !== "number"
  ) {
    throw new Error("DayAheadPricePoint has invalid fields");
  }
  return {
    start: record.start,
    end: record.end,
    eur_per_mwh: record.eur_per_mwh,
  };
}

export function parseDayAheadPriceSeries(value: unknown): DayAheadPriceSeries {
  if (typeof value !== "object" || value === null) {
    throw new Error("DayAheadPriceSeries must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.date !== "string" ||
    typeof record.source !== "string" ||
    typeof record.stale !== "boolean" ||
    typeof record.unit !== "string" ||
    typeof record.attribution !== "string" ||
    !Array.isArray(record.prices)
  ) {
    throw new Error("DayAheadPriceSeries has invalid fields");
  }
  return {
    date: record.date,
    source: record.source,
    stale: record.stale,
    unit: record.unit,
    attribution: record.attribution,
    prices: record.prices.map(parsePoint),
  };
}
