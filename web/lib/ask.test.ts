/** Ask-why answer parsing keeps the contract honest. */

import { describe, expect, it } from "vitest";
import { parseAskAnswer } from "./ask";

describe("parseAskAnswer", () => {
  it("parses answers with citations", () => {
    const payload = {
      question: "Warum so teuer?",
      answer: "Weil Umlagen anfallen [1].",
      citations: [
        {
          title: "KWKG-Umlage 2026",
          source_name: "netztransparenz.de",
          source_url: "https://example.de/kwkg",
        },
      ],
      model: "muse-spark-open",
    };
    expect(parseAskAnswer(payload)).toEqual(payload);
  });

  it("rejects malformed payloads", () => {
    expect(() => parseAskAnswer(null)).toThrow();
    expect(() => parseAskAnswer({ question: "x" })).toThrow();
    expect(() =>
      parseAskAnswer({
        question: "x",
        answer: "y",
        citations: [{ title: "t" }],
        model: "m",
      }),
    ).toThrow();
  });
});
