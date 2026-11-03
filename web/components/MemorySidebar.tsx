"use client";

/** Memory sidebar with preferences, episodes, and forget buttons. */

import { useCallback, useEffect, useState } from "react";
import {
  fetchHistory,
  fetchPreferences,
  forgetPreference,
} from "../lib/api";
import { collapseEpisodes, formatEpisodeText } from "../lib/memory";
import type { MemoryEpisode, PreferencesMap } from "../lib/memory";
import { formatDeviceName } from "../lib/format";
import { useLang } from "../lib/i18n";
import { useSession } from "../lib/session";

export default function MemorySidebar() {
  const { t, lang } = useLang();
  const { me, loading } = useSession();
  const verdictLabel: Record<string, string> = {
    good: t.feedbackGood,
    too_early: t.feedbackEarly,
    too_late: t.feedbackLate,
  };

  function episodeText(text: string): string {
    return formatEpisodeText(text, lang, verdictLabel);
  }

  const prefLabel: Record<string, string> = {
    annual_kwh: t.memoryAnnual,
    learned_windows: t.memoryLearned,
    devices: t.memoryDevices,
    quiet_hours: t.memoryQuiet,
  };

  function isEmpty(value: unknown): boolean {
    if (value === null || value === undefined || value === "") return true;
    if (typeof value === "number") return value === 0;
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === "object") return Object.keys(value).length === 0;
    return false;
  }

  function prefText(key: string, value: unknown): string {
    if (key === "annual_kwh" && typeof value === "number") {
      return `${value} kWh`;
    }
    if (key === "learned_windows" && typeof value === "object" && value !== null) {
      const count = Object.keys(value).length;
      return `${count} ${t.memoryDevices.toLowerCase()}`;
    }
    if (key === "quiet_hours" && typeof value === "object" && value !== null) {
      const range = value as { start?: unknown; end?: unknown };
      if (typeof range.start === "string" && typeof range.end === "string") {
        return `${range.start} – ${range.end}`;
      }
    }
    if (Array.isArray(value)) {
      const items = value.map(String);
      const shown =
        key === "devices"
          ? items.map((name) => formatDeviceName(name, lang))
          : items;
      return shown.join(", ");
    }
    return JSON.stringify(value) ?? "";
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
    if (!loading && me) refresh();
    const onMemory = () => refresh();
    window.addEventListener("strompilot:memory", onMemory);
    return () => {
      window.removeEventListener("strompilot:memory", onMemory);
    };
  }, [refresh, loading, me]);

  async function forget(key: string) {
    await forgetPreference(key);
    refresh();
  }

  const keys = me
    ? Object.keys(prefs.preferences).filter(
        (key) => key !== "consent" && !isEmpty(prefs.preferences[key]),
      )
    : [];
  const shownEpisodes = me ? episodes : [];
  return (
    <aside className="sidebar" aria-label={t.memoryTitle}>
      <h2>{t.memoryTitle}</h2>
      {me && error && <p className="error">{error}</p>}
      {!me && <p className="muted">{t.memoryEmpty}</p>}
      {me && keys.length === 0 && shownEpisodes.length === 0 && (
        <p className="muted">{t.memoryEmpty}</p>
      )}
      <ul>
        {keys.map((key) => (
          <li key={key} className="memory-row">
            <span>
              <strong>{prefLabel[key] ?? key}</strong>:{" "}
              {prefText(key, prefs.preferences[key])}
            </span>
            <button type="button" className="ghost" onClick={() => forget(key)}>
              {t.forget}
            </button>
          </li>
        ))}
      </ul>
      <ul>
        {collapseEpisodes(shownEpisodes).map((row) => (
          <li key={row.episode.id} className="muted">
            {episodeText(row.episode.text)}
            {row.count > 1 && (
              <span className="repeat-count"> ×{row.count}</span>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
