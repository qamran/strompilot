/** Memory types mirroring api/strompilot/memory/models.py. */

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
