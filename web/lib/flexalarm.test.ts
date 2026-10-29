import { describe, expect, it } from "vitest";
import { parseAlertsResponse, parseWatchReport } from "./flexalarm";

describe("flexalarm mirrors", () => {
  it("accepts a recorded watch report", () => {
    const payload = {
      household_id: "h1",
      day: "2026-06-01",
      candidates: 2,
      fired: 2,
      held: 0,
      delivered: 2,
      released: 0,
      skipped: 0,
      duplicates: 0,
      errors: [],
    };
    expect(parseWatchReport(payload)).toEqual(payload);
  });

  it("accepts a recorded alerts listing", () => {
    const payload = {
      household_id: "h1",
      alerts: [
        {
          id: 1,
          household_id: "h1",
          dedup_key: "h1:2026-06-01:cheap_window:02:00-04:00",
          kind: "cheap_window",
          title: "Billigstrom",
          body: "Von 02:00 bis 04:00 Uhr.",
          status: "delivered",
          channel: "log",
          reason: "gut",
          created_at: "2026-06-01T12:00:00+00:00",
        },
      ],
    };
    expect(parseAlertsResponse(payload)).toEqual(payload);
  });

  it("rejects malformed payloads", () => {
    expect(() => parseWatchReport(null)).toThrow();
    expect(() => parseWatchReport({ household_id: "h1" })).toThrow();
    expect(() => parseAlertsResponse(null)).toThrow();
    expect(() =>
      parseAlertsResponse({ household_id: "h1", alerts: [{ id: 1 }] }),
    ).toThrow();
  });
});
