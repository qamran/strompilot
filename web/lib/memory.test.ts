import { describe, expect, it } from "vitest";

import {
  collapseEpisodes,
  formatEpisodeText,
  parseEpisodesList,
  parsePreferencesMap,
} from "./memory";
import type { MemoryEpisode } from "./memory";

const VERDICTS = {
  good: "Just right",
  too_early: "Too early",
  too_late: "Too late",
};

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

  it("merges repeats anywhere in the list, newest first", () => {
    const rows = collapseEpisodes([
      episode(3, "E-Auto: good"),
      episode(2, "Herd: good"),
      episode(1, "E-Auto: good"),
    ]);
    expect(rows.map((row) => [row.episode.id, row.count])).toEqual([
      [3, 2],
      [2, 1],
    ]);
  });

  it("keeps different kinds apart", () => {
    const note = (id: number, text: string): MemoryEpisode => ({
      id,
      household_id: "h1",
      kind: "note",
      text,
      created_at: "2026-10-30T10:00:00+00:00",
    });
    const rows = collapseEpisodes([
      episode(1, "E-Auto: good"),
      note(2, "E-Auto: good"),
    ]);
    expect(rows.map((row) => row.count)).toEqual([1, 1]);
  });

  it("collapses an empty list to nothing", () => {
    expect(collapseEpisodes([])).toEqual([]);
  });
});

describe("formatEpisodeText", () => {
  it("localizes the device and verdict of feedback rows", () => {
    expect(formatEpisodeText("Waschmaschine: good", "en", VERDICTS)).toBe(
      "washing machine: Just right",
    );
    expect(formatEpisodeText("E-Auto: too_early", "de", VERDICTS)).toBe(
      "E-Auto: Too early",
    );
  });

  it("leaves free text without a known verdict alone", () => {
    expect(formatEpisodeText("mag Abende", "en", VERDICTS)).toBe("mag Abende");
    expect(formatEpisodeText("Herd: maybe", "en", VERDICTS)).toBe("Herd: maybe");
  });
});
