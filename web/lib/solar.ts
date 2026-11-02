/** Solar teaser types mirroring the /solar endpoints. */

export interface RoofBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number | null;
}

export interface RoofEstimate {
  roof_share: number;
  roof_m2: number | null;
  usable_m2: number | null;
  panels: number | null;
  kwp: number | null;
  kwh_per_year: number | null;
  assumptions: string[];
}

export interface MeasureResponse {
  household_id: string;
  width: number;
  height: number;
  boxes: RoofBox[];
  estimate: RoofEstimate | null;
  note: string;
}

export interface PreviewResponse {
  household_id: string;
  style: string;
  image_data_url: string;
  ai_label: string;
}

function parseBox(value: unknown): RoofBox {
  if (typeof value !== "object" || value === null) {
    throw new Error("RoofBox must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.x1 !== "number" ||
    typeof record.y1 !== "number" ||
    typeof record.x2 !== "number" ||
    typeof record.y2 !== "number" ||
    (record.confidence !== null && typeof record.confidence !== "number")
  ) {
    throw new Error("RoofBox has invalid fields");
  }
  return {
    x1: record.x1,
    y1: record.y1,
    x2: record.x2,
    y2: record.y2,
    confidence: record.confidence,
  };
}

function optionalNumber(value: unknown, label: string): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "number") {
    throw new Error(`${label} must be a number or null`);
  }
  return value;
}

function parseEstimate(value: unknown): RoofEstimate {
  if (typeof value !== "object" || value === null) {
    throw new Error("RoofEstimate must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.roof_share !== "number" ||
    !Array.isArray(record.assumptions) ||
    !record.assumptions.every((item) => typeof item === "string")
  ) {
    throw new Error("RoofEstimate has invalid fields");
  }
  return {
    roof_share: record.roof_share,
    roof_m2: optionalNumber(record.roof_m2, "roof_m2"),
    usable_m2: optionalNumber(record.usable_m2, "usable_m2"),
    panels: optionalNumber(record.panels, "panels"),
    kwp: optionalNumber(record.kwp, "kwp"),
    kwh_per_year: optionalNumber(record.kwh_per_year, "kwh_per_year"),
    assumptions: record.assumptions as string[],
  };
}

export function parseMeasureResponse(value: unknown): MeasureResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("MeasureResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    typeof record.width !== "number" ||
    typeof record.height !== "number" ||
    !Array.isArray(record.boxes) ||
    (record.estimate !== null && typeof record.estimate !== "object") ||
    typeof record.note !== "string"
  ) {
    throw new Error("MeasureResponse has invalid fields");
  }
  return {
    household_id: record.household_id,
    width: record.width,
    height: record.height,
    boxes: (record.boxes as unknown[]).map(parseBox),
    estimate:
      record.estimate === null ? null : parseEstimate(record.estimate),
    note: record.note,
  };
}

export function parsePreviewResponse(value: unknown): PreviewResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("PreviewResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    typeof record.style !== "string" ||
    typeof record.image_data_url !== "string" ||
    typeof record.ai_label !== "string"
  ) {
    throw new Error("PreviewResponse has invalid fields");
  }
  return {
    household_id: record.household_id,
    style: record.style,
    image_data_url: record.image_data_url,
    ai_label: record.ai_label,
  };
}
