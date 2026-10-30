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
    { label: t.navSchedule, hint: "/fahrplan", run: () => go("/fahrplan") },
    { label: t.navMeter, hint: "/zaehler", run: () => go("/zaehler") },
    { label: t.navAlarms, hint: "/alarme", run: () => go("/alarme") },
    { label: t.navAbout, hint: "/ueber", run: () => go("/ueber") },
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
      hint: "/alarme",
      run: () => {
        triggerWatch().catch(() => {});
        go("/alarme");
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
