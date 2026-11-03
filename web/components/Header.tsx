"use client";

/** Leitstand header with navigation and language switch. */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useLang } from "../lib/i18n";
import { useSession } from "../lib/session";

export default function Header({ alarmCount }: { alarmCount: number }) {
  const { t, lang, setLang } = useLang();
  const { me } = useSession();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const links = [
    { href: "/", label: t.navToday },
    { href: "/plan", label: t.navSchedule },
    { href: "/meter", label: t.navMeter },
    { href: "/alarms", label: t.navAlarms },
  ];
  const more = [
    { href: "/household", label: t.navHousehold },
    { href: "/solar", label: t.navSolar },
    { href: "/plan#report", label: t.navReport },
    { href: "/about", label: t.navAbout },
  ];
  const moreActive = more.some(({ href }) => pathname === href.split("#")[0]);
  return (
    <header className="topbar">
      <Link href="/" className="brand">
        STROMPILOT
      </Link>
      <button
        type="button"
        className="secondary menu-button"
        aria-expanded={open}
        aria-controls="main-nav"
        onClick={() => setOpen(!open)}
      >
        {t.menu}
      </button>
      <nav
        id="main-nav"
        className={open ? "open" : undefined}
        onClick={() => setOpen(false)}
      >
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            aria-current={pathname === link.href ? "page" : undefined}
            className={pathname === link.href ? "active" : undefined}
          >
            {link.label}
            {link.href === "/alarms" && me && alarmCount > 0 && (
              <span className="alarm-badge">{alarmCount}</span>
            )}
          </Link>
        ))}
        <details className="more-menu">
          <summary
            className={moreActive ? "active" : undefined}
            onClick={(event) => event.stopPropagation()}
          >
            {t.navMore}
          </summary>
          <div className="more-list">
            {more.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={
                  pathname === link.href.split("#")[0] ? "page" : undefined
                }
                className={
                  pathname === link.href.split("#")[0] ? "active" : undefined
                }
              >
                {link.label}
              </Link>
            ))}
          </div>
        </details>
      </nav>
      {me ? (
        <Link href="/account" className="account-link">
          {t.navAccount}
        </Link>
      ) : (
        <Link href="/signin" className="account-link">
          {t.navSignIn}
        </Link>
      )}
      <div className="lang-switch" aria-label={t.language}>
        <button
          type="button"
          disabled={lang === "de"}
          onClick={() => setLang("de")}
        >
          DE
        </button>
        <span>|</span>
        <button
          type="button"
          disabled={lang === "en"}
          onClick={() => setLang("en")}
        >
          EN
        </button>
      </div>
    </header>
  );
}
