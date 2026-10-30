"use client";

/** Zähler view: meter photo upload behind consent, readings, confirm. */

import { useEffect, useState } from "react";
import {
  confirmReading,
  fetchReadings,
  uploadMeterPhoto,
} from "../../lib/api";
import type { MeterReading } from "../../lib/meter";
import { useLang } from "../../lib/i18n";
import ConsentGate from "../../components/ConsentGate";

export default function MeterPage() {
  const { t } = useLang();
  const [readings, setReadings] = useState<MeterReading[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [consented, setConsented] = useState(false);
  const [keepPhoto, setKeepPhoto] = useState(false);
  const [corrected, setCorrected] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      setReadings(await fetchReadings());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    fetchReadings()
      .then(setReadings)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
  }, []);

  async function upload() {
    if (!file || !consented) return;
    try {
      await uploadMeterPhoto(file, keepPhoto);
      setFile(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function confirm(id: number) {
    try {
      const res = await confirmReading(
        id,
        corrected.trim() ? Number(corrected) : undefined,
      );
      setNote(res.note);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <section className="panel">
        <h2>{t.navMeter}</h2>
        <ConsentGate
          text={t.consentPhoto}
          storageKey="photo"
          onChange={setConsented}
        >
          {() => (
            <>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <label>
                <input
                  type="checkbox"
                  checked={keepPhoto}
                  onChange={(e) => setKeepPhoto(e.target.checked)}
                />{" "}
                {t.keepPhoto}
              </label>
              <button
                type="button"
                disabled={!file || !consented}
                onClick={upload}
              >
                {t.upload}
              </button>
            </>
          )}
        </ConsentGate>
        {error && <p className="error">{error}</p>}
        {note && <p className="muted">{note}</p>}
      </section>

      <section className="panel">
        <h2>{t.navMeter}</h2>
        <input
          value={corrected}
          onChange={(e) => setCorrected(e.target.value)}
          placeholder={t.correctedValue}
          inputMode="decimal"
        />
        <ul>
          {readings.map((reading) => (
            <li key={reading.id} className="memory-row">
              <span className="tabular">
                #{reading.id} · {reading.value_kwh} kWh · {reading.status} ·
                SAM {reading.sam_box ?? "–"}
              </span>
              {reading.status !== "confirmed" && (
                <button type="button" onClick={() => confirm(reading.id)}>
                  {t.confirm}
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
