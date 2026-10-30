"use client";

/** Memory sidebar with preferences, episodes, and forget buttons. */

import { useCallback, useEffect, useState } from "react";
import {
  fetchHistory,
  fetchPreferences,
  forgetPreference,
} from "../lib/api";
import type { MemoryEpisode, PreferencesMap } from "../lib/memory";
import { useLang } from "../lib/i18n";

export default function MemorySidebar() {
  const { t } = useLang();
  const verdictLabel: Record<string, string> = {
    good: t.feedbackGood,
    too_early: t.feedbackEarly,
    too_late: t.feedbackLate,
  };

  function episodeText(text: string): string {
    const cut = text.lastIndexOf(": ");
    if (cut < 0) return text;
    const label = verdictLabel[text.slice(cut + 2).trim()];
    return label ? `${text.slice(0, cut)}: ${label}` : text;
  }
  const [prefs, setPrefs] = useState<PreferencesMap>({
    household_id: "",
    preferences: {},
  });
  const [episodes, setEpisodes] = useState<MemoryEpisode[]>([]);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    Promise.all([fetchPreferences(), fetchHistory()])
      .then(([p, h]) => {
        setPrefs(p);
        setEpisodes(h.episodes.slice(0, 8));
        setError("");
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function forget(key: string) {
    await forgetPreference(key);
    refresh();
  }

  const keys = Object.keys(prefs.preferences);
  return (
    <aside className="sidebar" aria-label={t.memoryTitle}>
      <h2>{t.memoryTitle}</h2>
      {error && <p className="error">{error}</p>}
      {keys.length === 0 && episodes.length === 0 && (
        <p className="muted">{t.memoryEmpty}</p>
      )}
      <ul>
        {keys.map((key) => (
          <li key={key} className="memory-row">
            <span>
              <code>{key}</code>: {JSON.stringify(prefs.preferences[key])}
            </span>
            <button type="button" onClick={() => forget(key)}>
              {t.forget}
            </button>
          </li>
        ))}
      </ul>
      <ul>
        {episodes.map((episode) => (
          <li key={episode.id} className="muted">
            {episodeText(episode.text)}
          </li>
        ))}
      </ul>
    </aside>
  );
}
