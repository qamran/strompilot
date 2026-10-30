"use client";

/** Zähler view: meter photo upload behind consent, readings, confirm. */

import { useEffect, useState } from "react";
import {
  confirmReading,
  fetchReadings,
  readingPhotoUrl,
  uploadMeterPhoto,
} from "../../lib/api";
import type { MeterReading } from "../../lib/meter";
import { useLang } from "../../lib/i18n";
import ConsentGate from "../../components/ConsentGate";

export default function MeterPage() {
  const { t, lang } = useLang();
  const [readings, setReadings] = useState<MeterReading[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [consented, setConsented] = useState(false);
  const [keepPhoto, setKeepPhoto] = useState(false);
  const [corrected, setCorrected] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [uploadKey, setUploadKey] = useState(0);

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
      setUploadKey((key) => key + 1);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function confirm(id: number) {
    try {
      const res = await confirmReading(
        id,
        lang,
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
                key={uploadKey}
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
            <li key={reading.id} className="memory-row reading-row">
              {reading.photo_path && (
                // Consent-stored upload served by the API: no optimizer benefit.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  className="reading-photo"
                  src={readingPhotoUrl(reading.id)}
                  alt={`${t.meterPhoto} #${reading.id}`}
                />
              )}
              <span className="tabular">
                #{reading.id} · {reading.value_kwh} kWh · {reading.status} ·
                SAM{" "}
                {reading.sam_box ? t.meterDisplayFound : t.meterFullPhoto} ·{" "}
                {t.meterNumber} {reading.serial ?? "–"}
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
