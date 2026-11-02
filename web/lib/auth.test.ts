import { describe, expect, it } from "vitest";
import {
  parseMigrateResponse,
  parseRequestLinkResponse,
  parseSessionResponse,
} from "./auth";

describe("auth parsers", () => {
  it("parses a session with its household", () => {
    expect(
      parseSessionResponse({
        email: "lena@example.de",
        household_id: "hh_abc",
        expires_at: "2026-12-01T00:00:00+00:00",
      }),
    ).toEqual({
      email: "lena@example.de",
      household_id: "hh_abc",
      expires_at: "2026-12-01T00:00:00+00:00",
    });
  });

  it("rejects a session without a household", () => {
    expect(() =>
      parseSessionResponse({ email: "lena@example.de" }),
    ).toThrow();
  });

  it("parses a link receipt with and without a dev link", () => {
    expect(
      parseRequestLinkResponse({
        email: "lena@example.de",
        sent: true,
        dev_link: "http://x/auth/verify?token=abc",
      }).dev_link,
    ).toBe("http://x/auth/verify?token=abc");
    expect(
      parseRequestLinkResponse({ email: "lena@example.de", sent: true })
        .dev_link,
    ).toBeNull();
  });

  it("parses a migration receipt with counts", () => {
    expect(
      parseMigrateResponse({
        household_id: "hh_abc",
        migrated: { preferences: 1, episodes: 2, readings: 0, alerts: 0 },
      }).migrated.preferences,
    ).toBe(1);
  });
});
