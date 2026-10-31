"use client";

/** Leitstand header with navigation and language switch. */

import Link from "next/link";
import { useLang } from "../lib/i18n";

export default function Header({
  alarmCount,
  onPalette,
}: {
  alarmCount: number;
  onPalette: () => void;
}) {
  const { t, lang, setLang } = useLang();
  return (
    <header className="topbar">
      <Link href="/" className="brand">
        STROMPILOT
      </Link>
      <nav>
        <Link href="/">{t.navPrices}</Link>
        <Link href="/plan">{t.navSchedule}</Link>
        <Link href="/meter">{t.navMeter}</Link>
        <Link href="/alarms">
          {t.navAlarms}
          {alarmCount > 0 && <span className="alarm-badge">{alarmCount}</span>}
        </Link>
        <Link href="/about">{t.navAbout}</Link>
        <Link href="/household">{t.navHousehold}</Link>
      </nav>
      <button
        type="button"
        className="palette-hint"
        onClick={onPalette}
        title={t.paletteTitle}
      >
        {t.paletteHint}
      </button>
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
