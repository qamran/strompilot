"use client";

/** Command palette: Ctrl+K navigation and actions. */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLang } from "../lib/i18n";
import { triggerWatch } from "../lib/api";

interface Entry {
  label: string;
  hint: string;
  run: () => void;
}

export default function CommandPalette({ onClose }: { onClose: () => void }) {
  const { t, lang, setLang } = useLang();
  const router = useRouter();
  const [query, setQuery] = useState("");

  function go(path: string) {
    router.push(path);
    onClose();
  }

  const entries: Entry[] = [
    { label: t.navPrices, hint: "/", run: () => go("/") },
    { label: t.navSchedule, hint: "/plan", run: () => go("/plan") },
    { label: t.navMeter, hint: "/meter", run: () => go("/meter") },
    { label: t.navAlarms, hint: "/alarms", run: () => go("/alarms") },
    { label: t.navAbout, hint: "/about", run: () => go("/about") },
    { label: t.navHousehold, hint: "/household", run: () => go("/household") },
    {
      label: t.language,
      hint: lang === "de" ? "EN" : "DE",
      run: () => {
        setLang(lang === "de" ? "en" : "de");
        onClose();
      },
    },
    {
      label: t.watchNow,
      hint: "/alarms",
      run: () => {
        triggerWatch(lang).catch(() => {});
        go("/alarms");
      },
    },
  ];
  const needle = query.trim().toLowerCase();
  const shown = needle
    ? entries.filter((entry) => entry.label.toLowerCase().includes(needle))
    : entries;

  return (
    <div className="overlay" role="dialog" aria-label={t.paletteTitle}>
      <div className="overlay-card">
        <input
          autoFocus
          className="palette-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "Enter" && shown[0]) shown[0].run();
          }}
          placeholder={t.palettePlaceholder}
          aria-label={t.paletteTitle}
        />
        <ul className="palette-list">
          {shown.map((entry) => (
            <li key={entry.label}>
              <button type="button" onClick={entry.run}>
                {entry.label}
                <small>{entry.hint}</small>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
