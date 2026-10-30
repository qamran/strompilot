import { describe, expect, it } from "vitest";

import {
  collapseEpisodes,
  parseEpisodesList,
  parsePreferencesMap,
} from "./memory";
import type { MemoryEpisode } from "./memory";

describe("parsePreferencesMap", () => {
  it("parses a household preference map", () => {
    expect(
      parsePreferencesMap({
        household_id: "h1",
        preferences: { quiet_hours: { start: "22:00" } },
      }),
    ).toEqual({
      household_id: "h1",
      preferences: { quiet_hours: { start: "22:00" } },
    });
  });

  it("rejects invalid payloads", () => {
    expect(() => parsePreferencesMap(null)).toThrow();
    expect(() => parsePreferencesMap({ household_id: "h1" })).toThrow();
    expect(() =>
      parsePreferencesMap({ household_id: "h1", preferences: "no" }),
    ).toThrow();
  });
});

describe("parseEpisodesList", () => {
  it("parses a household episode list", () => {
    expect(
      parseEpisodesList({
        household_id: "h1",
        episodes: [
          {
            id: 2,
            household_id: "h1",
            kind: "feedback",
            text: "mag Abende",
            created_at: "2026-10-29T21:00:00+00:00",
          },
        ],
      }),
    ).toEqual({
      household_id: "h1",
      episodes: [
        {
          id: 2,
          household_id: "h1",
          kind: "feedback",
          text: "mag Abende",
          created_at: "2026-10-29T21:00:00+00:00",
        },
      ],
    });
  });

  it("rejects invalid payloads", () => {
    expect(() => parseEpisodesList(null)).toThrow();
    expect(() =>
      parseEpisodesList({ household_id: "h1", episodes: [{ id: "x" }] }),
    ).toThrow();
  });
});

describe("collapseEpisodes", () => {
  const episode = (id: number, text: string): MemoryEpisode => ({
    id,
    household_id: "h1",
    kind: "feedback",
    text,
    created_at: "2026-10-30T10:00:00+00:00",
  });

  it("collapses consecutive duplicates into one counted row", () => {
    const rows = collapseEpisodes([
      episode(1, "E-Auto: good"),
      episode(2, "E-Auto: good"),
      episode(3, "E-Auto: good"),
    ]);
    expect(rows).toEqual([{ episode: episode(1, "E-Auto: good"), count: 3 }]);
  });

  it("keeps order and restarts the count after a different row", () => {
    const rows = collapseEpisodes([
      episode(1, "E-Auto: good"),
      episode(2, "Herd: good"),
      episode(3, "E-Auto: good"),
    ]);
    expect(rows.map((row) => [row.episode.id, row.count])).toEqual([
      [1, 1],
      [2, 1],
      [3, 1],
    ]);
  });

  it("collapses an empty list to nothing", () => {
    expect(collapseEpisodes([])).toEqual([]);
  });
});
