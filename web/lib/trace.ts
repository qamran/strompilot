/** Agent trace parsing and model display names. */

import type { Lang } from "./i18n";

export interface TraceStep {
  stamp: string;
  node: string;
  model: string | null;
  detail: string;
}

const LINE = /^(\S+) (\w+)(?: · ([^:]+))?: (.*)$/;

export function parseTraceLine(line: string): TraceStep | null {
  const match = LINE.exec(line);
  if (!match) return null;
  return {
    stamp: match[1],
    node: match[2],
    model: match[3] ?? null,
    detail: match[4],
  };
}

const MODEL_NAMES: Record<string, string> = {
  "muse-spark-1.3": "Muse Spark",
  "muse-wonder-1.0": "Muse Wonder",
  "meta-models/muse-spark-open-1026": "Muse Spark Open",
};

export function friendlyModel(id: string, lang: Lang): string {
  if (id === "deterministic") {
    return lang === "de" ? "Deterministisch" : "Deterministic";
  }
  if (id === "none") {
    return lang === "de" ? "Nur Tarifhilfe" : "Guide only";
  }
  return MODEL_NAMES[id] ?? id;
}

export function stepDurationMs(
  current: string,
  previous: string | null,
): number | null {
  if (!previous) return null;
  const ms = new Date(current).getTime() - new Date(previous).getTime();
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

export function formatDuration(ms: number, lang: Lang): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toLocaleString(lang === "de" ? "de-DE" : "en-GB", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} s`;
}
