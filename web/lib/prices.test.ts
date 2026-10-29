import { describe, expect, it } from "vitest";
import { parseDayAheadPriceSeries } from "./prices";

describe("day-ahead price contract", () => {
  it("accepts a recorded series payload", () => {
    const payload = {
      date: "2026-10-29",
      source: "sample",
      stale: false,
      unit: "Eur/MWh",
      attribution: "Sample data for demo purposes - no live feed",
      prices: [
        {
          start: "2026-10-29T00:00:00+00:00",
          end: "2026-10-29T01:00:00+00:00",
          eur_per_mwh: 180.0,
        },
      ],
    };
    expect(parseDayAheadPriceSeries(payload)).toEqual(payload);
  });

  it("rejects malformed series payloads", () => {
    expect(() => parseDayAheadPriceSeries(null)).toThrow();
    expect(() => parseDayAheadPriceSeries({ date: "2026-10-29" })).toThrow();
    expect(() =>
      parseDayAheadPriceSeries({
        date: "2026-10-29",
        source: "sample",
        stale: false,
        unit: "Eur/MWh",
        attribution: "x",
        prices: [{ start: "a", end: "b", eur_per_mwh: "high" }],
      }),
    ).toThrow();
  });
});
