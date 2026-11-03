"use client";

/** "Why" overlay that replays the reasoning behind one schedule block. */

import { useEffect, useRef } from "react";
import type { PlanCitation, PlanSlot } from "../lib/plan";
import { useLang } from "../lib/i18n";
import { friendlyModel } from "../lib/trace";
import { formatCt, formatDeviceName, formatEur, formatKwh } from "../lib/format";

interface Props {
  slot: PlanSlot;
  citations: PlanCitation[];
  attribution?: Record<string, string>;
  onClose: () => void;
}

export default function WhyOverlay({
  slot,
  citations,
  attribution = {},
  onClose,
}: Props) {
  const { t, lang } = useLang();
  const cardRef = useRef<HTMLDivElement>(null);
  const related = citations.filter(
    (citation) =>
      citation.claim.includes(slot.device) || slot.reason.includes(citation.claim),
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !cardRef.current) return;
      const focusables = cardRef.current.querySelectorAll<HTMLElement>(
        'button, [href], [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    cardRef.current?.querySelector<HTMLElement>("button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const credits: Array<[string, string]> = [
    [t.pipe4Name, attribution["narration"] ?? ""],
    [t.pipe5Name, attribution["verdict"] ?? ""],
  ].filter(([, model]) => model !== "") as Array<[string, string]>;

  return (
    <div
      className="overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t.whyTitle}
      onClick={onClose}
    >
      <div
        className="overlay-card"
        ref={cardRef}
        onClick={(event) => event.stopPropagation()}
      >
        <h2>{t.whyTitle}</h2>
        <p>
          <strong>{formatDeviceName(slot.device, lang)}</strong> · {slot.start}–
          {slot.end}
        </p>
        <p>{slot.reason}</p>
        <ul className="facts">
          {slot.energy_kwh !== undefined && (
            <li>{formatKwh(slot.energy_kwh, lang)}</li>
          )}
          {slot.price_ct_kwh !== undefined && (
            <li>{formatCt(slot.price_ct_kwh, lang)}/kWh</li>
          )}
          {slot.cost_eur !== undefined && (
            <li>{formatEur(slot.cost_eur, lang)}</li>
          )}
        </ul>
        {related.length > 0 && (
          <ul className="citations">
            {related.map((citation) => (
              <li key={`${citation.claim}-${citation.source}`}>
                {citation.claim} — {citation.source}
                {citation.detail ? ` (${citation.detail})` : ""}
              </li>
            ))}
          </ul>
        )}
        {credits.length > 0 && (
          <p className="muted">
            {credits
              .map(([label, model]) => `${label} · ${friendlyModel(model, lang)}`)
              .join(" — ")}
          </p>
        )}
        <button type="button" onClick={onClose}>
          {t.close}
        </button>
      </div>
    </div>
  );
}
