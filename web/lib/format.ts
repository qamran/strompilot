/** Locale-aware number formatting with tabular figures. */

import type { Lang } from "./i18n";

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

/** Green / amber / red price semantics for the heatmap. */
export function priceClass(eurPerMwh: number, avg: number): string {
  if (eurPerMwh < 0) return "negative";
  if (eurPerMwh < avg * 0.7) return "cheap";
  if (eurPerMwh > avg * 1.3) return "spike";
  return "mid";
}
