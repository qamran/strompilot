/** Locale-aware number formatting with tabular figures. */

import type { Lang } from "./i18n";
import { allInCt, type DayAheadPricePoint } from "./prices";

export function formatCt(ctPerKwh: number, lang: Lang): string {
  return `${ctPerKwh.toLocaleString(lang === "de" ? "de-DE" : "en-GB", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} ct`;
}

export function formatEur(eur: number, lang: Lang): string {
  return `${eur.toLocaleString(lang === "de" ? "de-DE" : "en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} €`;
}

export function formatKwh(kwh: number, lang: Lang): string {
  return `${kwh.toLocaleString(lang === "de" ? "de-DE" : "en-GB", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} kWh`;
}

export type PriceClass = "negative" | "cheap" | "mid" | "spike";

export interface CheapestWindow {
  start: string;
  end: string;
  avgCt: number;
}

/**
 * Green / amber / red price semantics, ranked within the day.
 *
 * The cheapest quarter of hours reads cheap and the priciest sixth
 * reads spike, so a normal day always shows its shape. Negative
 * follows the spot market even though all-in figures stay positive.
 */
export function priceClass(
  spotEurPerMwh: number,
  valueCt: number,
  peersCt: number[],
): PriceClass {
  if (spotEurPerMwh < 0) return "negative";
  if (peersCt.length === 0) return "mid";
  const sorted = [...peersCt].sort((a, b) => a - b);
  if (sorted[sorted.length - 1] <= sorted[0]) return "mid";
  const cheapAt = sorted[Math.floor(0.25 * (sorted.length - 1))];
  const spikeAt = sorted[Math.ceil(0.85 * (sorted.length - 1))];
  if (valueCt <= cheapAt) return "cheap";
  if (valueCt >= spikeAt) return "spike";
  return "mid";
}

/** Cheapest consecutive block of one series, in all-in ct/kWh. */
export function cheapestWindow(
  points: DayAheadPricePoint[],
  span = 2,
): CheapestWindow | null {
  if (span <= 0 || points.length < span) return null;
  let best = 0;
  let bestAvg = Number.POSITIVE_INFINITY;
  for (let start = 0; start + span <= points.length; start += 1) {
    const slice = points.slice(start, start + span);
    const avg =
      slice.reduce((sum, point) => sum + allInCt(point), 0) / span;
    if (avg < bestAvg) {
      bestAvg = avg;
      best = start;
    }
  }
  return {
    start: points[best].start.slice(11, 16),
    end: points[best + span - 1].end.slice(11, 16),
    avgCt: bestAvg,
  };
}

/** Savings are only good news when they are actually positive. */
export function savingsClass(value: number): "positive" | "negative" {
  return value > 0 ? "positive" : "negative";
}

/** Short localized calendar day for an ISO date, never the raw string. */
export function formatDay(isoDate: string, lang: Lang): string {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString(
    lang === "de" ? "de-DE" : "en-GB",
    { day: "numeric", month: "short" },
  );
}

/** Full localized month name for an ISO month (YYYY-MM). */
export function formatMonthName(isoMonth: string, lang: Lang): string {
  return new Date(`${isoMonth}-01T12:00:00`).toLocaleDateString(
    lang === "de" ? "de-DE" : "en-GB",
    { month: "long" },
  );
}

const DEVICE_LABELS: Record<string, { de: string; en: string }> = {
  geschirrspueler: { de: "Geschirrspüler", en: "dishwasher" },
  "geschirrspüler": { de: "Geschirrspüler", en: "dishwasher" },
  dishwasher: { de: "Geschirrspüler", en: "dishwasher" },
  waschmaschine: { de: "Waschmaschine", en: "washing machine" },
  washingmachine: { de: "Waschmaschine", en: "washing machine" },
  eauto: { de: "E-Auto", en: "EV" },
  ev: { de: "E-Auto", en: "EV" },
  waermepumpe: { de: "Wärmepumpe", en: "heat pump" },
  "wärmepumpe": { de: "Wärmepumpe", en: "heat pump" },
  heatpump: { de: "Wärmepumpe", en: "heat pump" },
  trockner: { de: "Trockner", en: "dryer" },
  dryer: { de: "Trockner", en: "dryer" },
};

/**
 * Display name for a stored device key, per language.
 *
 * The backend folds umlauts and stores one canonical key; the UI
 * shows the readable name and keeps the key for writes.
 */
export function formatDeviceName(name: string, lang: Lang): string {
  const key = name.trim().toLowerCase().replace(/[\s_-]+/g, "");
  const hit = DEVICE_LABELS[key];
  if (hit) return lang === "de" ? hit.de : hit.en;
  return name.replace(/_/g, " ");
}
