import { describe, expect, it } from "vitest";

import { parseEpisodesList, parsePreferencesMap } from "./memory";

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
