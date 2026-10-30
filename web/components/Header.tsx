"use client";

/** Leitstand header with navigation and language switch. */

import Link from "next/link";
import { useLang } from "../lib/i18n";

export default function Header({ alarmCount }: { alarmCount: number }) {
  const { t, lang, setLang } = useLang();
  return (
    <header className="topbar">
      <Link href="/" className="brand">
        STROMPILOT
      </Link>
      <nav>
        <Link href="/">{t.navPrices}</Link>
        <Link href="/fahrplan">{t.navSchedule}</Link>
        <Link href="/zaehler">{t.navMeter}</Link>
        <Link href="/alarme">
          {t.navAlarms}
          {alarmCount > 0 && <span className="alarm-badge">{alarmCount}</span>}
        </Link>
        <Link href="/ueber">{t.navAbout}</Link>
      </nav>
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
