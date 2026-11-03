/** Memory types mirroring api/strompilot/memory/models.py. */

import { formatDeviceName } from "./format";
import type { Lang } from "./i18n";

export interface PreferencesMap {
  household_id: string;
  preferences: Record<string, unknown>;
}

export interface MemoryEpisode {
  id: number;
  household_id: string;
  kind: string;
  text: string;
  created_at: string;
}

export interface EpisodesList {
  household_id: string;
  episodes: MemoryEpisode[];
}

export function parsePreferencesMap(value: unknown): PreferencesMap {
  if (typeof value !== "object" || value === null) {
    throw new Error("PreferencesMap must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    typeof record.preferences !== "object" ||
    record.preferences === null ||
    Array.isArray(record.preferences)
  ) {
    throw new Error("PreferencesMap has invalid fields");
  }
  return {
    household_id: record.household_id,
    preferences: record.preferences as Record<string, unknown>,
  };
}

function parseEpisode(value: unknown): MemoryEpisode {
  if (typeof value !== "object" || value === null) {
    throw new Error("MemoryEpisode must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.id !== "number" ||
    typeof record.household_id !== "string" ||
    typeof record.kind !== "string" ||
    typeof record.text !== "string" ||
    typeof record.created_at !== "string"
  ) {
    throw new Error("MemoryEpisode has invalid fields");
  }
  return {
    id: record.id,
    household_id: record.household_id,
    kind: record.kind,
    text: record.text,
    created_at: record.created_at,
  };
}

export interface CollapsedEpisodes {
  episode: MemoryEpisode;
  count: number;
}

export function collapseEpisodes(
  episodes: MemoryEpisode[],
): CollapsedEpisodes[] {
  const rows: CollapsedEpisodes[] = [];
  const index = new Map<string, CollapsedEpisodes>();
  for (const episode of episodes) {
    const key = `${episode.kind}\n${episode.text}`;
    const found = index.get(key);
    if (found) {
      found.count += 1;
    } else {
      const row = { episode, count: 1 };
      rows.push(row);
      index.set(key, row);
    }
  }
  return rows;
}

/**
 * Display text for one episode: feedback rows ("device: verdict") get a
 * localized device and verdict, free text passes through untouched.
 */
export function formatEpisodeText(
  text: string,
  lang: Lang,
  verdicts: Record<string, string>,
): string {
  const cut = text.lastIndexOf(": ");
  if (cut < 0) return text;
  const label = verdicts[text.slice(cut + 2).trim()];
  if (!label) return text;
  const device = formatDeviceName(text.slice(0, cut).trim(), lang);
  return `${device}: ${label}`;
}

export function parseEpisodesList(value: unknown): EpisodesList {
  if (typeof value !== "object" || value === null) {
    throw new Error("EpisodesList must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    !Array.isArray(record.episodes)
  ) {
    throw new Error("EpisodesList has invalid fields");
  }
  return {
    household_id: record.household_id,
    episodes: record.episodes.map(parseEpisode),
  };
}
