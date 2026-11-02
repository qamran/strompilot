"use client";

/** Solar view: roof measuring plus renovation previews. */

import { useState } from "react";
import { measureRoof, previewStyle } from "../../lib/api";
import type { MeasureResponse, PreviewResponse } from "../../lib/solar";
import { useLang } from "../../lib/i18n";
import { useSession } from "../../lib/session";
import ConsentGate from "../../components/ConsentGate";
import SignInPrompt from "../../components/SignInPrompt";

const STYLES = ["solar", "heat_pump", "facade"] as const;

export default function SolarPage() {
  const { t, lang } = useLang();
  const { me, loading } = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [consented, setConsented] = useState(false);
  const [widthM, setWidthM] = useState("");
  const [measured, setMeasured] = useState<MeasureResponse | null>(null);
  const [photoUrl, setPhotoUrl] = useState("");
  const [style, setStyle] = useState<(typeof STYLES)[number]>("solar");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function pick(next: File | null) {
    setFile(next);
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoUrl(next ? URL.createObjectURL(next) : "");
    setMeasured(null);
    setPreview(null);
  }

  if (!loading && !me) {
    return <SignInPrompt />;
  }

  async function measure() {
    if (!file || !consented) return;
    setError("");
    setMeasured(null);
    setBusy(true);
    try {
      const parsedWidth = widthM.trim() ? Number(widthM) : undefined;
      setMeasured(await measureRoof(file, parsedWidth, lang));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function render() {
    if (!file || !consented) return;
    setError("");
    setPreview(null);
    setBusy(true);
    try {
      setPreview(await previewStyle(file, style, lang));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const styleLabel =
    style === "solar"
      ? t.styleSolar
      : style === "heat_pump"
        ? t.styleHeatPump
        : t.styleFacade;

  return (
    <>
      <section className="panel" aria-label={t.solarTitle}>
        <h2>{t.solarTitle}</h2>
        <p className="muted">{t.solarIntro}</p>
        <ConsentGate
          text={t.consentSolar}
          storageKey="solar"
          onChange={setConsented}
        >
          {() => (
            <>
              <div className="form-row">
                <label>
                  {t.housePhoto}{" "}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    onChange={(e) => pick(e.target.files?.[0] ?? null)}
                  />
                </label>
                <label>
                  {t.roofWidth}{" "}
                  <input
                    type="number"
                    min="1"
                    value={widthM}
                    onChange={(e) => setWidthM(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  disabled={!file || !consented || busy}
                  onClick={() => measure().catch(() => {})}
                >
                  {t.measureRoof}
                </button>
              </div>
            </>
          )}
        </ConsentGate>
        {error && <p className="error">{error}</p>}
        {measured?.note && <p className="muted">{measured.note}</p>}
        {measured && measured.boxes.length > 0 && photoUrl && (
          <div className="solar-frame">
            {/* Consent-gated local upload: no optimizer benefit. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={photoUrl} alt={t.housePhoto} />
            {measured.boxes.map((box, index) => (
              <span
                key={index}
                className="solar-box"
                style={{
                  left: `${(box.x1 / measured.width) * 100}%`,
                  top: `${(box.y1 / measured.height) * 100}%`,
                  width: `${((box.x2 - box.x1) / measured.width) * 100}%`,
                  height: `${((box.y2 - box.y1) / measured.height) * 100}%`,
                }}
              />
            ))}
          </div>
        )}
        {measured?.estimate && (
          <ul>
            <li className="memory-row">
              <span className="muted">{t.roofShare}</span>
              <span className="tabular">
                {(measured.estimate.roof_share * 100).toFixed(1)} %
              </span>
            </li>
            {measured.estimate.roof_m2 !== null && (
              <li className="memory-row">
                <span className="muted">{t.roofArea}</span>
                <span className="tabular">
                  {measured.estimate.roof_m2.toFixed(1)} m²
                </span>
              </li>
            )}
            {measured.estimate.usable_m2 !== null && (
              <li className="memory-row">
                <span className="muted">{t.usableArea}</span>
                <span className="tabular">
                  {measured.estimate.usable_m2.toFixed(1)} m²
                </span>
              </li>
            )}
            {measured.estimate.panels !== null && (
              <li className="memory-row">
                <span className="muted">{t.panelCount}</span>
                <span className="tabular">{measured.estimate.panels}</span>
              </li>
            )}
            {measured.estimate.kwp !== null && (
              <li className="memory-row">
                <span className="muted">{t.kwpLabel}</span>
                <span className="tabular">
                  {measured.estimate.kwp.toFixed(1)} kWp
                </span>
              </li>
            )}
            {measured.estimate.kwh_per_year !== null && (
              <li className="memory-row">
                <span className="muted">{t.yieldLabel}</span>
                <span className="tabular">
                  {Math.round(measured.estimate.kwh_per_year)} kWh
                </span>
              </li>
            )}
          </ul>
        )}
        {measured?.estimate && (
          <>
            <h3>{t.assumptionsTitle}</h3>
            <ul>
              {measured.estimate.assumptions.map((item) => (
                <li key={item} className="muted">
                  {item}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="panel" aria-label={t.styleTitle}>
        <h2>{t.styleTitle}</h2>
        <div className="style-row" role="group" aria-label={t.styleTitle}>
          {STYLES.map((name) => (
            <button
              key={name}
              type="button"
              className={name === style ? undefined : "secondary"}
              onClick={() => setStyle(name)}
            >
              {name === "solar"
                ? t.styleSolar
                : name === "heat_pump"
                  ? t.styleHeatPump
                  : t.styleFacade}
            </button>
          ))}
        </div>
        <button
          type="button"
          disabled={!file || !consented || busy}
          onClick={() => render().catch(() => {})}
        >
          {t.renderPreview}: {styleLabel}
        </button>
        {preview && (
          <>
            {/* AI-edited upload served as a data URL: no optimizer benefit. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              className="solar-preview"
              src={preview.image_data_url}
              alt={styleLabel}
            />
            <p>
              <span className="ai-label">{preview.ai_label}</span>
            </p>
          </>
        )}
      </section>
    </>
  );
}
