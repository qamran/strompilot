"use client";

/** "Why" overlay that replays the reasoning behind one schedule block. */

import type { PlanCitation, PlanSlot } from "../lib/plan";
import { useLang } from "../lib/i18n";
import { formatCt, formatEur, formatKwh } from "../lib/format";

interface Props {
  slot: PlanSlot;
  citations: PlanCitation[];
  onClose: () => void;
}

export default function WhyOverlay({ slot, citations, onClose }: Props) {
  const { t, lang } = useLang();
  const related = citations.filter(
    (citation) =>
      citation.claim.includes(slot.device) || slot.reason.includes(citation.claim),
  );
  return (
    <div className="overlay" role="dialog" aria-label={t.whyTitle}>
      <div className="overlay-card">
        <h2>{t.whyTitle}</h2>
        <p>
          <strong>{slot.device}</strong> · {slot.start}–{slot.end}
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
        <button type="button" onClick={onClose}>
          {t.close}
        </button>
      </div>
    </div>
  );
}
