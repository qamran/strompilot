/** Smoke suite: recorded fixtures parse and key views render. */

import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import React from "react";
import { parseDayAheadPriceSeries } from "../lib/prices";
import { parsePlanDetail } from "../lib/plan";
import { parseAlertsResponse } from "../lib/flexalarm";
import { parseReadingsResponse } from "../lib/meter";
import { parseMonthlyReportResponse } from "../lib/report";
import { parseWallboxStatus } from "../lib/wallbox";
import { parseEpisodesList, parsePreferencesMap } from "../lib/memory";
import { LangProvider } from "../lib/i18n";
import Heatmap from "../components/Heatmap";
import Odometer from "../components/Odometer";
import WhyOverlay from "../components/WhyOverlay";
import GlassBox from "../components/GlassBox";
import SourceChip from "../components/SourceChip";
import pricesFixture from "../fixtures/prices.json";
import planFixture from "../fixtures/plan.json";
import alertsFixture from "../fixtures/alerts.json";
import readingsFixture from "../fixtures/readings.json";
import reportFixture from "../fixtures/report.json";
import wallboxFixture from "../fixtures/wallbox.json";
import preferencesFixture from "../fixtures/preferences.json";
import historyFixture from "../fixtures/history.json";

function withLang(node: React.ReactNode): string {
  return renderToString(React.createElement(LangProvider, null, node));
}

describe("recorded fixtures", () => {
  it("parses the price day", () => {
    const series = parseDayAheadPriceSeries(pricesFixture);
    expect(series.prices.length).toBe(24);
  });

  it("parses the paused plan", () => {
    const plan = parsePlanDetail(planFixture);
    expect(plan.status).toBe("paused");
    expect(plan.schedule?.[0].device).toBe("Waschmaschine");
  });

  it("parses alerts, readings, and wallbox", () => {
    expect(parseAlertsResponse(alertsFixture).alerts.length).toBe(1);
    expect(parseReadingsResponse(readingsFixture).readings.length).toBe(1);
    expect(parseWallboxStatus(wallboxFixture).plugged).toBe(true);
  });

  it("parses the monthly report and memory", () => {
    const report = parseMonthlyReportResponse(reportFixture);
    expect(report.report.days.length).toBeGreaterThan(27);
    expect(parsePreferencesMap(preferencesFixture).household_id).toBe(
      "demo-haushalt",
    );
    expect(parseEpisodesList(historyFixture).episodes.length).toBe(1);
  });
});

describe("key views on fixtures", () => {
  it("renders the heatmap canvas", () => {
    const series = parseDayAheadPriceSeries(pricesFixture);
    const html = withLang(React.createElement(Heatmap, { series }));
    expect(html).toContain("<canvas");
    expect(html).toContain(series.date);
  });

  it("renders the odometer with the report savings", () => {
    const report = parseMonthlyReportResponse(reportFixture);
    const html = withLang(
      React.createElement(Odometer, { value: report.report.savings_eur }),
    );
    expect(html).toContain("odometer");
  });

  it("renders the why overlay for the planned block", () => {
    const plan = parsePlanDetail(planFixture);
    const slot = plan.schedule?.[0];
    if (!slot) throw new Error("fixture has no slot");
    const html = withLang(
      React.createElement(WhyOverlay, {
        slot,
        citations: plan.citations ?? [],
        onClose: () => {},
      }),
    );
    expect(html).toContain("Waschmaschine");
    expect(html).toContain("02:00");
  });

  it("renders glass-box drawers and source chips", () => {
    const html = withLang(
      React.createElement(GlassBox, {
        label: "Ø",
        value: "15,0 ct/kWh",
        formula: "x = 1",
        source: "test",
      }),
    );
    expect(html).toContain("Formel");
    const chip = withLang(
      React.createElement(SourceChip, { source: "sample" }),
    );
    expect(chip).toContain("Beispieldaten");
  });
});
