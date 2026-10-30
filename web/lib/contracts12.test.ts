import { describe, expect, it } from "vitest";
import { parsePlanCreated, parsePlanDetail } from "./plan";
import {
  parseIllustrationResponse,
  parseMonthlyReportResponse,
} from "./report";
import { parseWallboxStatus } from "./wallbox";

describe("plan mirrors", () => {
  it("accepts a recorded plan detail", () => {
    const payload = {
      thread_id: "abc",
      status: "paused",
      schedule: [
        {
          device: "Waschmaschine",
          start: "02:00",
          end: "04:00",
          reason: "billig",
          energy_kwh: 4.0,
          price_ct_kwh: 15.0,
          cost_eur: 0.6,
        },
      ],
      narration: "Text",
      citations: [{ claim: "c", source: "s", detail: "d" }],
      total_cost_eur: 0.6,
      error: null,
      audit: ["a b: c"],
    };
    expect(parsePlanDetail(payload)).toEqual(payload);
    expect(
      parsePlanCreated({ thread_id: "abc", status: "running" }),
    ).toEqual({ thread_id: "abc", status: "running" });
  });

  it("rejects malformed payloads", () => {
    expect(() => parsePlanDetail(null)).toThrow();
    expect(() => parsePlanDetail({ thread_id: "a" })).toThrow();
    expect(() => parsePlanCreated({})).toThrow();
  });
});

describe("report mirrors", () => {
  it("accepts a recorded monthly report", () => {
    const report = {
      month: "2026-02",
      annual_kwh: 3650.0,
      days: [
        {
          day: "2026-02-01",
          kwh: 10.0,
          cost_eur: 3.0,
          cheapest_window: { start: "02:00", end: "04:00", avg_ct_kwh: 15.0 },
          sample: false,
        },
      ],
      total_kwh: 10.0,
      total_cost_eur: 3.0,
      savings_eur: 1.0,
      flat_ct_kwh: 40.0,
      worst_hour: { day: "2026-02-01", hour: 18, price_ct_kwh: 45.0 },
      sample_days: 0,
      assumptions: ["a"],
    };
    expect(
      parseMonthlyReportResponse({ report, illustration_data_url: null }),
    ).toEqual({ report, illustration_data_url: null });
    expect(
      parseIllustrationResponse({
        month: "2026-02",
        illustration_data_url: "data:image/png;base64,x",
        cached: true,
      }).cached,
    ).toBe(true);
  });

  it("rejects malformed payloads", () => {
    expect(() => parseMonthlyReportResponse(null)).toThrow();
    expect(() => parseIllustrationResponse({})).toThrow();
  });
});

describe("wallbox mirrors", () => {
  it("accepts a recorded wallbox status", () => {
    const payload = {
      plugged: true,
      charging: true,
      power_kw: 11.0,
      max_kw: 11.0,
      session_kwh: 5.5,
      total_kwh: 5.5,
      sim_now: "2026-06-01T00:30:00+02:00",
      program: {
        start: "2026-06-01T00:00:00+02:00",
        end: "2026-06-01T04:00:00+02:00",
        max_kw: 11.0,
      },
    };
    expect(parseWallboxStatus(payload)).toEqual(payload);
  });

  it("rejects malformed payloads", () => {
    expect(() => parseWallboxStatus(null)).toThrow();
    expect(() => parseWallboxStatus({ plugged: true })).toThrow();
  });
});
