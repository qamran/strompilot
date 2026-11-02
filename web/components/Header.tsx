"use client";

/** Leitstand header with navigation and language switch. */

import Link from "next/link";
import { useLang } from "../lib/i18n";
import { useSession } from "../lib/session";

export default function Header({
  alarmCount,
  onPalette,
}: {
  alarmCount: number;
  onPalette: () => void;
}) {
  const { t, lang, setLang } = useLang();
  const { me } = useSession();
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
          {me && alarmCount > 0 && (
            <span className="alarm-badge">{alarmCount}</span>
          )}
        </Link>
        <Link href="/about">{t.navAbout}</Link>
        <Link href="/household">{t.navHousehold}</Link>
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
