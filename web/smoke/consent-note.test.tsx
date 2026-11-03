/** Smoke suite: the consent note reflects the server-side state. */

import { describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import React from "react";
import { LangProvider } from "../lib/i18n";
import ConsentNote from "../components/ConsentNote";

let consent: boolean | null = null;

vi.mock("next/link", () => ({
  default: function FakeLink({
    href,
    children,
  }: {
    href: string;
    children?: React.ReactNode;
  }) {
    return <a href={href}>{children}</a>;
  },
}));

vi.mock("../lib/session", () => ({
  useSession: () => ({
    me:
      consent === null
        ? null
        : {
            email: "a@b.de",
            household_id: "h1",
            expires_at: "2026-12-01",
            consent_agreed: consent,
          },
    loading: false,
    refresh: async () => {},
  }),
}));

function render() {
  return renderToString(
    React.createElement(
      LangProvider,
      null,
      React.createElement(ConsentNote, null),
    ),
  );
}

describe("consent note", () => {
  it("shows the agreed state with a manage link", () => {
    consent = true;
    const html = render();
    expect(html).toContain("Planning consent agreed.");
    expect(html).toContain('href="/household"');
  });

  it("shows the missing state when consent is absent", () => {
    consent = false;
    const html = render();
    expect(html).toContain("Planning needs your consent.");
  });

  it("renders nothing without a session", () => {
    consent = null;
    expect(render()).not.toContain("Planning consent");
  });
});
