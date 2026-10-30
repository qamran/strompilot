/** Plan types mirroring the /plan endpoints in main.py. */

export interface PlanCreated {
  thread_id: string;
  status: string;
}

export interface PlanSlot {
  device: string;
  start: string;
  end: string;
  reason: string;
  energy_kwh?: number;
  price_ct_kwh?: number;
  cost_eur?: number;
}

export interface PlanCitation {
  claim: string;
  source: string;
  detail: string;
}

export interface PlanDetail {
  thread_id: string;
  status: string;
  schedule: PlanSlot[] | null;
  narration: string | null;
  citations: PlanCitation[] | null;
  total_cost_eur: number | null;
  error: string | null;
  audit: string[];
}

function asRecord(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    throw new Error(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function parseSlot(value: unknown): PlanSlot {
  const record = asRecord(value, "PlanSlot");
  if (
    typeof record.device !== "string" ||
    typeof record.start !== "string" ||
    typeof record.end !== "string" ||
    typeof record.reason !== "string"
  ) {
    throw new Error("PlanSlot has invalid fields");
  }
  const slot: PlanSlot = {
    device: record.device,
    start: record.start,
    end: record.end,
    reason: record.reason,
  };
  if (typeof record.energy_kwh === "number") slot.energy_kwh = record.energy_kwh;
  if (typeof record.price_ct_kwh === "number")
    slot.price_ct_kwh = record.price_ct_kwh;
  if (typeof record.cost_eur === "number") slot.cost_eur = record.cost_eur;
  return slot;
}

function parseCitation(value: unknown): PlanCitation {
  const record = asRecord(value, "PlanCitation");
  if (
    typeof record.claim !== "string" ||
    typeof record.source !== "string" ||
    typeof record.detail !== "string"
  ) {
    throw new Error("PlanCitation has invalid fields");
  }
  return {
    claim: record.claim,
    source: record.source,
    detail: record.detail,
  };
}

export function parsePlanCreated(value: unknown): PlanCreated {
  const record = asRecord(value, "PlanCreated");
  if (typeof record.thread_id !== "string" || typeof record.status !== "string") {
    throw new Error("PlanCreated has invalid fields");
  }
  return { thread_id: record.thread_id, status: record.status };
}

export function parsePlanDetail(value: unknown): PlanDetail {
  const record = asRecord(value, "PlanDetail");
  if (
    typeof record.thread_id !== "string" ||
    typeof record.status !== "string" ||
    (record.schedule !== null && !Array.isArray(record.schedule)) ||
    (record.narration !== null && typeof record.narration !== "string") ||
    (record.citations !== null && !Array.isArray(record.citations)) ||
    (record.total_cost_eur !== null && typeof record.total_cost_eur !== "number") ||
    (record.error !== null && typeof record.error !== "string") ||
    !Array.isArray(record.audit)
  ) {
    throw new Error("PlanDetail has invalid fields");
  }
  return {
    thread_id: record.thread_id,
    status: record.status,
    schedule:
      record.schedule === null
        ? null
        : (record.schedule as unknown[]).map(parseSlot),
    narration: record.narration as string | null,
    citations:
      record.citations === null
        ? null
        : (record.citations as unknown[]).map(parseCitation),
    total_cost_eur: record.total_cost_eur as number | null,
    error: record.error as string | null,
    audit: (record.audit as unknown[]).map(String),
  };
}
