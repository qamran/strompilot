import { describe, expect, it } from "vitest";
import { parseConfirmResponse, parseReadingsResponse } from "./meter";

describe("meter mirrors", () => {
  it("accepts a recorded readings listing", () => {
    const payload = {
      household_id: "h1",
      readings: [
        {
          id: 1,
          household_id: "h1",
          value_kwh: 4217.3,
          read_at: "2026-06-01T08:00:00+00:00",
          status: "proposed",
          confidence: "high",
          sam_box: "10,10,90,90",
          photo_path: "/data/meter_photos/abc.png",
          created_at: "2026-06-01T08:00:01+00:00",
        },
      ],
    };
    expect(parseReadingsResponse(payload)).toEqual(payload);
  });

  it("accepts a recorded confirm response", () => {
    const totals = {
      day: "2026-06-02",
      annual_kwh: 3500.0,
      device_cost_eur: 0.6,
      baseline_kwh: 9.5,
      baseline_cost_eur: 2.85,
      total_eur: 3.45,
      slots: 1,
    };
    const payload = {
      reading: {
        id: 2,
        household_id: "h1",
        value_kwh: 4227.3,
        read_at: "2026-06-02T08:00:00+00:00",
        status: "confirmed",
        confidence: "high",
        sam_box: null,
        photo_path: "/data/meter_photos/def.png",
        created_at: "2026-06-02T08:00:01+00:00",
      },
      calibration: {
        annual_kwh: 3650.0,
        kwh_per_day: 10.0,
        days: 1.0,
        from_reading_id: 1,
        to_reading_id: 2,
      },
      diff: {
        before: totals,
        after: { ...totals, annual_kwh: 3650.0 },
        devices_unchanged: true,
        note: "Hintergrund alt gegen neu.",
      },
      note: "Hintergrund alt gegen neu.",
    };
    expect(parseConfirmResponse(payload)).toEqual(payload);
  });

  it("rejects malformed payloads", () => {
    expect(() => parseReadingsResponse(null)).toThrow();
    expect(() =>
      parseReadingsResponse({ household_id: "h1", readings: [{ id: 1 }] }),
    ).toThrow();
    expect(() => parseConfirmResponse(null)).toThrow();
    expect(() => parseConfirmResponse({ note: "x" })).toThrow();
  });
});
