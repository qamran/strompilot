/** Meter vision types mirroring the /meter endpoints in main.py. */

export interface MeterReading {
  id: number;
  household_id: string;
  value_kwh: number;
  read_at: string;
  status: string;
  confidence: string;
  sam_box: string | null;
  photo_path: string;
  serial: string | null;
  created_at: string;
}

export interface ReadingsResponse {
  household_id: string;
  readings: MeterReading[];
}

export interface Calibration {
  annual_kwh: number;
  kwh_per_day: number;
  days: number;
  from_reading_id: number;
  to_reading_id: number;
}

export interface PlanTotals {
  day: string;
  annual_kwh: number;
  device_cost_eur: number;
  baseline_kwh: number;
  baseline_cost_eur: number;
  total_eur: number;
  slots: number;
}

export interface ReplanDiff {
  before: PlanTotals;
  after: PlanTotals;
  devices_unchanged: boolean;
  note: string;
}

export interface ConfirmResponse {
  reading: MeterReading;
  calibration: Calibration | null;
  diff: ReplanDiff | null;
  note: string;
}

function parseReading(value: unknown): MeterReading {
  if (typeof value !== "object" || value === null) {
    throw new Error("MeterReading must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.id !== "number" ||
    typeof record.household_id !== "string" ||
    typeof record.value_kwh !== "number" ||
    typeof record.read_at !== "string" ||
    typeof record.status !== "string" ||
    typeof record.confidence !== "string" ||
    (record.sam_box !== null && typeof record.sam_box !== "string") ||
    typeof record.photo_path !== "string" ||
    (record.serial !== null &&
      record.serial !== undefined &&
      typeof record.serial !== "string") ||
    typeof record.created_at !== "string"
  ) {
    throw new Error("MeterReading has invalid fields");
  }
  return {
    id: record.id,
    household_id: record.household_id,
    value_kwh: record.value_kwh,
    read_at: record.read_at,
    status: record.status,
    confidence: record.confidence,
    sam_box: record.sam_box,
    photo_path: record.photo_path,
    serial:
      record.serial === undefined || record.serial === null
        ? null
        : record.serial,
    created_at: record.created_at,
  };
}

export function parseReadingsResponse(value: unknown): ReadingsResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("ReadingsResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    !Array.isArray(record.readings)
  ) {
    throw new Error("ReadingsResponse has invalid fields");
  }
  return {
    household_id: record.household_id,
    readings: record.readings.map(parseReading),
  };
}

function parseCalibration(value: unknown): Calibration {
  if (typeof value !== "object" || value === null) {
    throw new Error("Calibration must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.annual_kwh !== "number" ||
    typeof record.kwh_per_day !== "number" ||
    typeof record.days !== "number" ||
    typeof record.from_reading_id !== "number" ||
    typeof record.to_reading_id !== "number"
  ) {
    throw new Error("Calibration has invalid fields");
  }
  return {
    annual_kwh: record.annual_kwh,
    kwh_per_day: record.kwh_per_day,
    days: record.days,
    from_reading_id: record.from_reading_id,
    to_reading_id: record.to_reading_id,
  };
}

function parseTotals(value: unknown): PlanTotals {
  if (typeof value !== "object" || value === null) {
    throw new Error("PlanTotals must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.day !== "string" ||
    typeof record.annual_kwh !== "number" ||
    typeof record.device_cost_eur !== "number" ||
    typeof record.baseline_kwh !== "number" ||
    typeof record.baseline_cost_eur !== "number" ||
    typeof record.total_eur !== "number" ||
    typeof record.slots !== "number"
  ) {
    throw new Error("PlanTotals has invalid fields");
  }
  return {
    day: record.day,
    annual_kwh: record.annual_kwh,
    device_cost_eur: record.device_cost_eur,
    baseline_kwh: record.baseline_kwh,
    baseline_cost_eur: record.baseline_cost_eur,
    total_eur: record.total_eur,
    slots: record.slots,
  };
}

function parseDiff(value: unknown): ReplanDiff {
  if (typeof value !== "object" || value === null) {
    throw new Error("ReplanDiff must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.before !== "object" ||
    typeof record.after !== "object" ||
    typeof record.devices_unchanged !== "boolean" ||
    typeof record.note !== "string"
  ) {
    throw new Error("ReplanDiff has invalid fields");
  }
  return {
    before: parseTotals(record.before),
    after: parseTotals(record.after),
    devices_unchanged: record.devices_unchanged,
    note: record.note,
  };
}

export function parseConfirmResponse(value: unknown): ConfirmResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("ConfirmResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.reading !== "object" ||
    (record.calibration !== null && typeof record.calibration !== "object") ||
    (record.diff !== null && typeof record.diff !== "object") ||
    typeof record.note !== "string"
  ) {
    throw new Error("ConfirmResponse has invalid fields");
  }
  return {
    reading: parseReading(record.reading),
    calibration:
      record.calibration === null
        ? null
        : parseCalibration(record.calibration),
    diff: record.diff === null ? null : parseDiff(record.diff),
    note: record.note,
  };
}
