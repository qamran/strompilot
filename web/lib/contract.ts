/** Typed API contract stub mirroring api/strompilot/contract.py. */

export const CONTRACT_VERSION = "0.4.0";

export interface HealthResponse {
  status: string;
  service: string;
  contract_version: string;
}

export function parseHealthResponse(value: unknown): HealthResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("HealthResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.status !== "string" ||
    typeof record.service !== "string" ||
    typeof record.contract_version !== "string"
  ) {
    throw new Error("HealthResponse has invalid fields");
  }
  return {
    status: record.status,
    service: record.service,
    contract_version: record.contract_version,
  };
}
