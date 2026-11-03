import { describe, expect, it } from "vitest";
import {
  cheapestWindow,
  formatDay,
  formatDeviceName,
  formatMonthName,
  priceClass,
  savingsClass,
  type PriceClass,
} from "./format";
import type { DayAheadPricePoint } from "./prices";

/** A normal German day: 210 to 328 EUR/MWh, average around 260. */
function reviewDay(): { spot: number[]; allIn: number[] } {
  const spot = [
    228, 220, 215, 210, 214, 225, 248, 272, 290, 298, 285, 262, 250, 244, 248,
    258, 272, 298, 320, 328, 315, 290, 262, 240,
  ];
  const allIn = spot.map((v) => v / 10 + 21.3);
  return { spot, allIn };
}

function point(hour: number, allInCt: number): DayAheadPricePoint {
  const start = `2026-11-02T${String(hour).padStart(2, "0")}:00:00+00:00`;
  const end = `2026-11-02T${String(hour + 1).padStart(2, "0")}:00:00+00:00`;
  return { start, end, eur_per_mwh: allInCt * 10, all_in_ct_kwh: allInCt };
}

describe("priceClass", () => {
  it("spreads a normal day across cheap, mid, and spike", () => {
    const { spot, allIn } = reviewDay();
    const classes = new Set<PriceClass>(
      spot.map((v, i) => priceClass(v, allIn[i], allIn)),
    );
    expect(classes).toEqual(new Set(["cheap", "mid", "spike"]));
  });

  it("marks roughly the cheapest quarter of hours as cheap", () => {
    const { spot, allIn } = reviewDay();
    const cheap = spot.filter((v, i) => priceClass(v, allIn[i], allIn) === "cheap");
    expect(cheap.length).toBe(6);
  });

  it("calls every bar mid on a flat day", () => {
    const peers = new Array(24).fill(45.0);
    for (const value of peers) {
      expect(priceClass(240.0, value, peers)).toBe("mid");
    }
  });

  it("flags negative spot hours even when all-in stays positive", () => {
    const peers = new Array(24).fill(40.0);
    expect(priceClass(-12.5, 15.4, peers)).toBe("negative");
  });
});

describe("cheapestWindow", () => {
  it("finds the cheapest two-hour block", () => {
    const { allIn } = reviewDay();
    const points = allIn.map((ct, hour) => point(hour, ct));
    const found = cheapestWindow(points, 2);
    expect(found?.start).toBe("03:00");
    expect(found?.end).toBe("05:00");
    expect(found?.avgCt).toBeCloseTo((allIn[3] + allIn[4]) / 2, 5);
  });

  it("returns null without enough hours", () => {
    expect(cheapestWindow([], 2)).toBeNull();
    expect(cheapestWindow([point(0, 30)], 2)).toBeNull();
  });
});

describe("savingsClass", () => {
  it("is positive only for real savings", () => {
    expect(savingsClass(5.2)).toBe("positive");
    expect(savingsClass(-19.33)).toBe("negative");
    expect(savingsClass(0)).toBe("negative");
  });
});

describe("formatDeviceName", () => {
  it("labels known devices per language", () => {
    expect(formatDeviceName("Geschirrspueler", "en")).toBe("dishwasher");
    expect(formatDeviceName("Geschirrspueler", "de")).toBe("Geschirrspüler");
    expect(formatDeviceName("E-Auto", "en")).toBe("EV");
    expect(formatDeviceName("E-Auto", "de")).toBe("E-Auto");
    expect(formatDeviceName("Waschmaschine", "en")).toBe("washing machine");
  });

  it("passes unknown devices through readably", () => {
    expect(formatDeviceName("pool_pump", "en")).toBe("pool pump");
    expect(formatDeviceName("Sauna", "de")).toBe("Sauna");
  });
});

describe("formatDay", () => {
  it("localizes ISO dates", () => {
    expect(formatDay("2026-11-02", "en")).toBe("2 Nov");
    expect(formatDay("2026-11-02", "de")).toBe("2. Nov.");
  });
});

describe("formatMonthName", () => {
  it("localizes ISO months", () => {
    expect(formatMonthName("2026-11", "en")).toBe("November");
    expect(formatMonthName("2026-11", "de")).toBe("November");
    expect(formatMonthName("2026-03", "de")).toBe("März");
  });
});
