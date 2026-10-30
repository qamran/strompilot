"use client";

/** Preise view: sentence-to-plan entry, heatmap, savings, wallbox strip. */

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  fetchMonthlyReport,
  fetchPrices,
  fetchWallbox,
  startPlan,
} from "../lib/api";
import type { DayAheadPriceSeries } from "../lib/prices";
import type { WallboxStatus } from "../lib/wallbox";
import { useLang } from "../lib/i18n";
import { formatCt } from "../lib/format";
import Heatmap from "../components/Heatmap";
import Odometer from "../components/Odometer";
import SourceChip from "../components/SourceChip";
import GlassBox from "../components/GlassBox";
import ConsentGate from "../components/ConsentGate";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function PricesPage() {
  const { t, lang } = useLang();
  const router = useRouter();
  const [series, setSeries] = useState<DayAheadPriceSeries | null>(null);
  const [savings, setSavings] = useState(0);
  const [wallbox, setWallbox] = useState<WallboxStatus | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchPrices()
      .then(setSeries)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
    fetchMonthlyReport(currentMonth())
      .then((res) => setSavings(res.report.savings_eur))
      .catch(() => setSavings(0));
    fetchWallbox()
      .then(setWallbox)
      .catch(() => setWallbox(null));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    try {
      const created = await startPlan(text.trim());
      router.push(`/fahrplan?thread=${encodeURIComponent(created.thread_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const avg =
    series && series.prices.length > 0
      ? series.prices.reduce((sum, p) => sum + p.eur_per_mwh, 0) /
        series.prices.length /
        10
      : 0;

  return (
    <>
      <section className="panel">
        <p className="muted">{t.tagline}</p>
        <ConsentGate text={t.consentPlan}>
          {() => (
            <form className="plan-form" onSubmit={submit}>
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={t.planPlaceholder}
                aria-label={t.planButton}
              />
              <button type="submit">{t.planButton}</button>
            </form>
          )}
        </ConsentGate>
        <p className="muted">{t.planHint}</p>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="panel">
        <h2>
          {t.today}
          {series && <SourceChip source={series.source} />}
        </h2>
        {series && <Heatmap series={series} />}
        {series && (
          <GlassBox
            label={t.avg}
            value={`${formatCt(avg, lang)}/kWh`}
            formula="Ø = Σ Preis(h) / 24"
            source={series.attribution}
          />
        )}
        <p className="muted">{t.quarterHourNote}</p>
      </section>

      <section className="panel">
        <h2>
          {t.savingsMonth} <Odometer value={savings} />
          {t.perMonth}
        </h2>
        <p className="muted">{t.estimateLabel}</p>
      </section>

      {wallbox && (
        <section className="panel">
          <h2>{t.wallbox}</h2>
          <p>
            {!wallbox.plugged && t.unplugged}
            {wallbox.plugged &&
              (wallbox.charging
                ? `${t.charging} ${wallbox.power_kw} kW`
                : t.idle)}
            {wallbox.plugged &&
              ` · ${wallbox.session_kwh.toFixed(1)} kWh ${t.today.toLowerCase()}`}
          </p>
        </section>
      )}
    </>
  );
}
