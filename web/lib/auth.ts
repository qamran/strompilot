/** Auth types mirroring api/strompilot/auth endpoints. */

export interface SessionInfo {
  email: string;
  household_id: string;
  expires_at: string;
}

export interface RequestLinkReceipt {
  email: string;
  sent: boolean;
  dev_link: string | null;
}

export interface MigrateReceipt {
  household_id: string;
  migrated: Record<string, number>;
}

export function parseSessionResponse(value: unknown): SessionInfo {
  if (typeof value !== "object" || value === null) {
    throw new Error("SessionResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.email !== "string" ||
    typeof record.household_id !== "string" ||
    typeof record.expires_at !== "string"
  ) {
    throw new Error("SessionResponse has invalid fields");
  }
  return {
    email: record.email,
    household_id: record.household_id,
    expires_at: record.expires_at,
  };
}

export function parseRequestLinkResponse(value: unknown): RequestLinkReceipt {
  if (typeof value !== "object" || value === null) {
    throw new Error("RequestLinkResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.email !== "string" ||
    typeof record.sent !== "boolean" ||
    (record.dev_link !== undefined &&
      record.dev_link !== null &&
      typeof record.dev_link !== "string")
  ) {
    throw new Error("RequestLinkResponse has invalid fields");
  }
  return {
    email: record.email,
    sent: record.sent,
    dev_link:
      typeof record.dev_link === "string" ? record.dev_link : null,
  };
}

export function parseMigrateResponse(value: unknown): MigrateReceipt {
  if (typeof value !== "object" || value === null) {
    throw new Error("MigrateResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    typeof record.migrated !== "object" ||
    record.migrated === null ||
    Array.isArray(record.migrated)
  ) {
    throw new Error("MigrateResponse has invalid fields");
  }
  const migrated: Record<string, number> = {};
  for (const [key, count] of Object.entries(
    record.migrated as Record<string, unknown>,
  )) {
    if (typeof count !== "number") {
      throw new Error("MigrateResponse has invalid counts");
    }
    migrated[key] = count;
  }
  return { household_id: record.household_id, migrated };
}
