import { describe, expect, it } from "vitest";
import { parseFeedbackListResponse, parseFeedbackResponse } from "./feedback";

describe("feedback mirrors", () => {
  it("accepts a recorded feedback response", () => {
    const payload = {
      household_id: "h1",
      episode: {
        id: 1,
        household_id: "h1",
        kind: "feedback",
        text: "Waschmaschine: too_early",
        created_at: "2026-06-01T12:00:00+00:00",
      },
      learned_windows: {
        Waschmaschine: { earliest_shift_h: 1, latest_shift_h: 0 },
      },
    };
    expect(parseFeedbackResponse(payload)).toEqual(payload);
  });

  it("accepts a recorded feedback listing", () => {
    const payload = {
      household_id: "h1",
      feedback: [
        {
          id: 1,
          household_id: "h1",
          kind: "feedback",
          text: "E-Auto: too_late",
          created_at: "2026-06-01T12:00:00+00:00",
        },
      ],
    };
    expect(parseFeedbackListResponse(payload)).toEqual(payload);
  });

  it("rejects malformed payloads", () => {
    expect(() => parseFeedbackResponse(null)).toThrow();
    expect(() =>
      parseFeedbackResponse({
        household_id: "h1",
        episode: { id: 1 },
        learned_windows: {},
      }),
    ).toThrow();
    expect(() => parseFeedbackListResponse(null)).toThrow();
    expect(() =>
      parseFeedbackListResponse({ household_id: "h1", feedback: [{ id: 1 }] }),
    ).toThrow();
  });
});
