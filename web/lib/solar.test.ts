import { describe, expect, it } from "vitest";
import { parseMeasureResponse, parsePreviewResponse } from "./solar";

describe("solar parsers", () => {
  it("parses a roof measurement with its estimate", () => {
    expect(
      parseMeasureResponse({
        household_id: "h1",
        width: 800,
        height: 600,
        boxes: [{ x1: 1, y1: 2, x2: 3, y2: 4, confidence: 0.9 }],
        estimate: {
          roof_share: 0.16,
          roof_m2: 50,
          usable_m2: 35,
          panels: 17,
          kwp: 6.8,
          kwh_per_year: 6460,
          assumptions: ["straight-on"],
        },
        note: "",
      }).estimate?.panels,
    ).toBe(17);
  });

  it("parses a roof miss with its note", () => {
    const parsed = parseMeasureResponse({
      household_id: "h1",
      width: 800,
      height: 600,
      boxes: [],
      estimate: null,
      note: "No roof found.",
    });
    expect(parsed.estimate).toBeNull();
    expect(parsed.note).toBe("No roof found.");
  });

  it("rejects a measurement without dimensions", () => {
    expect(() =>
      parseMeasureResponse({ household_id: "h1", boxes: [] }),
    ).toThrow();
  });

  it("parses a renovation preview with its label", () => {
    const parsed = parsePreviewResponse({
      household_id: "h1",
      style: "solar",
      image_data_url: "data:image/png;base64,AAA",
      ai_label: "AI visualization",
    });
    expect(parsed.style).toBe("solar");
    expect(parsed.ai_label).toContain("AI");
  });
});
