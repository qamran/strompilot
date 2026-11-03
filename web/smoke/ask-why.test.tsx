/** Smoke suite: the Ask-Why box renders its input and button. */

import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import React from "react";
import { LangProvider } from "../lib/i18n";
import AskWhy from "../components/AskWhy";

describe("ask why", () => {
  it("renders the question input with a submit button", () => {
    const html = renderToString(
      React.createElement(
        LangProvider,
        null,
        React.createElement(AskWhy, null),
      ),
    );
    expect(html).toContain("Ask why");
    expect(html).toContain("Why is my price higher than the spot price?");
    expect(html).toContain("Ask");
    expect(html).toContain('type="submit"');
  });
});
