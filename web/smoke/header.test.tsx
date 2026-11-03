/** Smoke suite: header marks the active page and labels its menu. */

import { describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import React from "react";
import { LangProvider } from "../lib/i18n";
import Header from "../components/Header";

vi.mock("next/link", () => ({
  default: function FakeLink({
    href,
    children,
    className,
    "aria-current": current,
  }: {
    href: string;
    children?: React.ReactNode;
    className?: string;
    "aria-current"?: "page";
  }) {
    return (
      <a href={href} className={className} aria-current={current}>
        {children}
      </a>
    );
  },
}));

vi.mock("next/navigation", () => ({ usePathname: () => "/plan" }));

describe("header", () => {
  it("marks the current page and exposes the mobile menu", () => {
    const html = renderToString(
      React.createElement(
        LangProvider,
        null,
        React.createElement(Header, { alarmCount: 0 }),
      ),
    );
    expect(html).toContain('aria-current="page"');
    expect(html).toContain('href="/plan"');
    expect(html).toContain("Menu");
    expect(html).toContain('id="main-nav"');
  });

  it("keeps four top links and moves the rest under More", () => {
    const html = renderToString(
      React.createElement(
        LangProvider,
        null,
        React.createElement(Header, { alarmCount: 0 }),
      ),
    );
    expect(html).toContain("Today");
    expect(html).toContain("More");
    expect(html).toContain('href="/household"');
    expect(html).toContain('href="/solar"');
    expect(html).toContain('href="/about"');
    expect(html).toContain('href="/plan#report"');
    expect(html).not.toContain("Ctrl+K");
  });
});
