/** Approval types mirroring the /approvals endpoints in main.py. */

export interface ApprovalSlot {
  device: string;
  start: string;
  end: string;
  reason: string;
  energy_kwh?: number;
  price_ct_kwh?: number;
  cost_eur?: number;
}

export interface ApprovalReview {
  type: string;
  schedule: ApprovalSlot[];
  total_cost_eur: number;
  narration: string;
}

export interface ApprovalStatus {
  thread_id: string;
  status: string;
  published: boolean;
  review: ApprovalReview | null;
  error: string | null;
}

function parseSlot(value: unknown): ApprovalSlot {
  if (typeof value !== "object" || value === null) {
    throw new Error("ApprovalSlot must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.device !== "string" ||
    typeof record.start !== "string" ||
    typeof record.end !== "string" ||
    typeof record.reason !== "string"
  ) {
    throw new Error("ApprovalSlot has invalid fields");
  }
  const slot: ApprovalSlot = {
    device: record.device,
    start: record.start,
    end: record.end,
    reason: record.reason,
  };
  if (typeof record.energy_kwh === "number") {
    slot.energy_kwh = record.energy_kwh;
  }
  if (typeof record.price_ct_kwh === "number") {
    slot.price_ct_kwh = record.price_ct_kwh;
  }
  if (typeof record.cost_eur === "number") {
    slot.cost_eur = record.cost_eur;
  }
  return slot;
}

function parseReview(value: unknown): ApprovalReview {
  if (typeof value !== "object" || value === null) {
    throw new Error("ApprovalReview must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.type !== "string" ||
    !Array.isArray(record.schedule) ||
    typeof record.total_cost_eur !== "number" ||
    typeof record.narration !== "string"
  ) {
    throw new Error("ApprovalReview has invalid fields");
  }
  return {
    type: record.type,
    schedule: record.schedule.map(parseSlot),
    total_cost_eur: record.total_cost_eur,
    narration: record.narration,
  };
}

export function parseApprovalStatus(value: unknown): ApprovalStatus {
  if (typeof value !== "object" || value === null) {
    throw new Error("ApprovalStatus must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.thread_id !== "string" ||
    typeof record.status !== "string" ||
    typeof record.published !== "boolean" ||
    (record.review !== null && typeof record.review !== "object") ||
    (record.error !== null && typeof record.error !== "string")
  ) {
    throw new Error("ApprovalStatus has invalid fields");
  }
  return {
    thread_id: record.thread_id,
    status: record.status,
    published: record.published,
    review: record.review === null ? null : parseReview(record.review),
    error: record.error === null ? null : (record.error as string),
  };
}
