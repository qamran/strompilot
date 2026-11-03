/** Smoke suite: the plan input form supports first run and retry. */

import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import React from "react";
import PlanInputForm from "../components/PlanInputForm";

function render(submitLabel: string, disabled: boolean) {
  return renderToString(
    React.createElement(PlanInputForm, {
      text: "Night shift",
      onText: () => {},
      onSubmit: () => {},
      submitLabel,
      placeholder: "Describe your day …",
      disabled,
    }),
  );
}

describe("plan input form", () => {
  it("renders the sentence input with a submit label", () => {
    const html = render("Make a plan", false);
    expect(html).toContain("Night shift");
    expect(html).toContain("Make a plan");
    expect(html).not.toContain("disabled");
  });

  it("renders the retry label for failed runs", () => {
    const html = render("Try again", false);
    expect(html).toContain("Try again");
    expect(html).toContain('type="submit"');
  });

  it("disables the submit without consent", () => {
    const html = render("Make a plan", true);
    expect(html).toContain("disabled");
  });
});
