import { describe, expect, it } from "vitest";
import { parseQuietRange } from "./quiet";

describe("parseQuietRange", () => {
  it("reads a valid overnight range", () => {
    expect(parseQuietRange({ start: "22:00", end: "06:00" })).toEqual({
      start: "22:00",
      end: "06:00",
    });
  });

  it("rejects anything else", () => {
    expect(parseQuietRange(null)).toBeNull();
    expect(parseQuietRange({})).toBeNull();
    expect(parseQuietRange({ start: "22:00", end: "soon" })).toBeNull();
    expect(parseQuietRange({ start: "22:00", end: "22:00" })).toBeNull();
    expect(parseQuietRange("22:00-06:00")).toBeNull();
  });
});
