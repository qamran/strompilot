"use client";

/** Household view: manage devices, quiet hours, annual use, memories. */

import { useEffect, useState } from "react";
import {
  deleteEpisode,
  fetchHistory,
  fetchPreferences,
  forgetHousehold,
  savePreference,
} from "../../lib/api";
import type { MemoryEpisode } from "../../lib/memory";
import { useLang } from "../../lib/i18n";

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

export default function HouseholdPage() {
  const { t } = useLang();
  const [devices, setDevices] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [quietStart, setQuietStart] = useState("");
  const [quietEnd, setQuietEnd] = useState("");
  const [annual, setAnnual] = useState("");
  const [episodes, setEpisodes] = useState<MemoryEpisode[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [armed, setArmed] = useState(false);

  async function load() {
    try {
      const prefs = await fetchPreferences();
      const stored = prefs.preferences["devices"];
      setDevices(Array.isArray(stored) ? stored.map(String) : []);
      const quiet = prefs.preferences["quiet_hours"] as
        | { start?: unknown; end?: unknown }
        | undefined;
      setQuietStart(typeof quiet?.start === "string" ? quiet.start : "");
      setQuietEnd(typeof quiet?.end === "string" ? quiet.end : "");
      const use = prefs.preferences["annual_kwh"];
      setAnnual(typeof use === "number" && use > 0 ? String(use) : "");
      const history = await fetchHistory();
      setEpisodes(history.episodes);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    let live = true;
    fetchPreferences()
      .then((prefs) => {
        if (!live) return;
        const stored = prefs.preferences["devices"];
        setDevices(Array.isArray(stored) ? stored.map(String) : []);
        const quiet = prefs.preferences["quiet_hours"] as
          | { start?: unknown; end?: unknown }
          | undefined;
        setQuietStart(typeof quiet?.start === "string" ? quiet.start : "");
        setQuietEnd(typeof quiet?.end === "string" ? quiet.end : "");
        const use = prefs.preferences["annual_kwh"];
        setAnnual(typeof use === "number" && use > 0 ? String(use) : "");
        return fetchHistory();
      })
      .then((history) => {
        if (live && history) setEpisodes(history.episodes);
      })
      .catch((err: unknown) => {
        if (live) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      live = false;
    };
  }, []);

  async function run(action: () => Promise<void>) {
    setError("");
    setNote("");
    try {
      await action();
      setNote(t.saved);
      await load();
      window.dispatchEvent(new Event("strompilot:memory"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function addDevice() {
    const name = draft.trim();
    if (!name || devices.includes(name)) return;
    setDraft("");
    const next = [...devices, name];
    setDevices(next);
    await run(() => savePreference("devices", next));
  }

  async function removeDevice(name: string) {
    const next = devices.filter((device) => device !== name);
    setDevices(next);
    await run(() => savePreference("devices", next));
  }

  async function saveQuiet() {
    if (!TIME.test(quietStart) || !TIME.test(quietEnd)) return;
    await run(() =>
      savePreference("quiet_hours", { start: quietStart, end: quietEnd }),
    );
  }

  async function saveAnnual() {
    const value = Number(annual);
    if (!Number.isFinite(value) || value <= 0) return;
    await run(() => savePreference("annual_kwh", value));
  }

  async function removeEpisode(id: number) {
    await run(() => deleteEpisode(id));
  }

  async function forget() {
    if (!armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    await run(async () => {
      await forgetHousehold();
      setNote(t.dangerDone);
    });
  }

  return (
    <>
      <section className="panel">
        <h2>{t.householdTitle}</h2>
        <p className="muted">{t.householdIntro}</p>
        {note && <p className="flash">{note}</p>}
        {error && <p className="error">{error}</p>}
      </section>
      <section className="panel" aria-label={t.devicesTitle}>
        <h2>{t.devicesTitle}</h2>
        {devices.length === 0 && <p className="muted">{t.devicesEmpty}</p>}
        <ul>
          {devices.map((device) => (
            <li key={device} className="memory-row">
              <span>{device}</span>
              <button type="button" onClick={() => removeDevice(device)}>
                {t.remove}
              </button>
            </li>
          ))}
        </ul>
        <div className="form-row">
          <input
            type="text"
            value={draft}
            placeholder={t.devicePlaceholder}
            aria-label={t.devicePlaceholder}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") addDevice().catch(() => {});
            }}
          />
          <button type="button" onClick={() => addDevice().catch(() => {})}>
            {t.addDevice}
          </button>
        </div>
      </section>
      <section className="panel" aria-label={t.quietTitle}>
        <h2>{t.quietTitle}</h2>
        <p className="muted">{t.quietHint}</p>
        <div className="form-row">
          <label>
            {t.quietStart}{" "}
            <input
              type="time"
              value={quietStart}
              onChange={(event) => setQuietStart(event.target.value)}
            />
          </label>
          <label>
            {t.quietEnd}{" "}
            <input
              type="time"
              value={quietEnd}
              onChange={(event) => setQuietEnd(event.target.value)}
            />
          </label>
          <button type="button" onClick={() => saveQuiet().catch(() => {})}>
            {t.save}
          </button>
        </div>
      </section>
      <section className="panel" aria-label={t.annualTitle}>
        <h2>{t.annualTitle}</h2>
        <p className="muted">{t.annualHint}</p>
        <div className="form-row">
          <input
            type="number"
            min={1}
            value={annual}
            placeholder={t.annualPlaceholder}
            aria-label={t.annualTitle}
            onChange={(event) => setAnnual(event.target.value)}
          />
          <button type="button" onClick={() => saveAnnual().catch(() => {})}>
            {t.save}
          </button>
        </div>
      </section>
      <section className="panel" aria-label={t.memoriesTitle}>
        <h2>{t.memoriesTitle}</h2>
        {episodes.length === 0 && <p className="muted">{t.memoriesEmpty}</p>}
        <ul>
          {episodes.map((episode) => (
            <li key={episode.id} className="memory-row">
              <span className="muted">{episode.text}</span>
              <button type="button" onClick={() => removeEpisode(episode.id)}>
                {t.remove}
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="panel danger" aria-label={t.dangerTitle}>
        <h2>{t.dangerTitle}</h2>
        <p className="muted">{t.dangerBody}</p>
        <button
          type="button"
          className={armed ? "armed" : ""}
          onClick={() => forget().catch(() => {})}
        >
          {armed ? t.dangerConfirm : t.dangerArm}
        </button>
      </section>
    </>
  );
}
