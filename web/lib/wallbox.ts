/** Wallbox types mirroring the /wallbox endpoints in main.py. */

export interface ChargeProgram {
  start: string;
  end: string;
  max_kw: number;
}

export interface WallboxStatus {
  plugged: boolean;
  charging: boolean;
  power_kw: number;
  max_kw: number;
  session_kwh: number;
  total_kwh: number;
  sim_now: string;
  program: ChargeProgram | null;
}

function asRecord(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    throw new Error(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function parseProgram(value: unknown): ChargeProgram {
  const record = asRecord(value, "ChargeProgram");
  if (
    typeof record.start !== "string" ||
    typeof record.end !== "string" ||
    typeof record.max_kw !== "number"
  ) {
    throw new Error("ChargeProgram has invalid fields");
  }
  return { start: record.start, end: record.end, max_kw: record.max_kw };
}

export function parseWallboxStatus(value: unknown): WallboxStatus {
  const record = asRecord(value, "WallboxStatus");
  if (
    typeof record.plugged !== "boolean" ||
    typeof record.charging !== "boolean" ||
    typeof record.power_kw !== "number" ||
    typeof record.max_kw !== "number" ||
    typeof record.session_kwh !== "number" ||
    typeof record.total_kwh !== "number" ||
    typeof record.sim_now !== "string" ||
    (record.program !== null && typeof record.program !== "object")
  ) {
    throw new Error("WallboxStatus has invalid fields");
  }
  return {
    plugged: record.plugged,
    charging: record.charging,
    power_kw: record.power_kw,
    max_kw: record.max_kw,
    session_kwh: record.session_kwh,
    total_kwh: record.total_kwh,
    sim_now: record.sim_now,
    program: record.program === null ? null : parseProgram(record.program),
  };
}
