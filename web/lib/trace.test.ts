import { describe, expect, it } from "vitest";
import {
  formatDuration,
  friendlyModel,
  parseTraceLine,
  stepDurationMs,
} from "./trace";

describe("parseTraceLine", () => {
  it("reads a model-attributed line", () => {
    const step = parseTraceLine(
      "2026-11-02T15:26:56.123+00:00 critic · muse-wonder-1.0: approved",
    );
    expect(step).toEqual({
      stamp: "2026-11-02T15:26:56.123+00:00",
      node: "critic",
      model: "muse-wonder-1.0",
      detail: "approved",
    });
  });

  it("reads legacy lines without a model", () => {
    const step = parseTraceLine(
      "2026-11-02T15:26:56+00:00 critic: approved",
    );
    expect(step?.model).toBeNull();
    expect(step?.detail).toBe("approved");
  });

  it("rejects garbage", () => {
    expect(parseTraceLine("hello")).toBeNull();
    expect(parseTraceLine("")).toBeNull();
  });
});

describe("friendlyModel", () => {
  it("names the known models", () => {
    expect(friendlyModel("muse-spark-1.3", "en")).toBe("Muse Spark");
    expect(friendlyModel("muse-wonder-1.0", "de")).toBe("Muse Wonder");
    expect(friendlyModel("meta-models/muse-spark-open-1026", "en")).toBe(
      "Muse Spark Open",
    );
    expect(friendlyModel("deterministic", "de")).toBe("Deterministisch");
    expect(friendlyModel("deterministic", "en")).toBe("Deterministic");
    expect(friendlyModel("none", "de")).toBe("Nur Tarifhilfe");
    expect(friendlyModel("none", "en")).toBe("Guide only");
  });

  it("passes unknown ids through", () => {
    expect(friendlyModel("future-model-9", "en")).toBe("future-model-9");
  });
});

describe("stepDurationMs", () => {
  it("diffs consecutive stamps", () => {
    expect(
      stepDurationMs(
        "2026-11-02T15:26:56.123+00:00",
        "2026-11-02T15:26:47.000+00:00",
      ),
    ).toBe(9123);
    expect(stepDurationMs("2026-11-02T15:26:56.123+00:00", null)).toBeNull();
    expect(stepDurationMs("nope", "2026-11-02T15:26:47.000+00:00")).toBeNull();
  });

  it("formats durations per locale", () => {
    expect(formatDuration(9123, "en")).toBe("9.1 s");
    expect(formatDuration(9123, "de")).toBe("9,1 s");
    expect(formatDuration(120, "en")).toBe("120 ms");
  });
});
