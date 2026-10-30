"use client";

/** Preise view: price-now hero, plan entry, heatmap, savings, wallbox. */

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
import { formatCt, priceClass } from "../lib/format";
import Heatmap from "../components/Heatmap";
import Odometer from "../components/Odometer";
import SourceChip from "../components/SourceChip";
import GlassBox from "../components/GlassBox";
import ConsentGate from "../components/ConsentGate";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function currentPoint(series: DayAheadPriceSeries): number {
  const hour = new Date().getHours();
  const match = series.prices.find(
    (point) => Number(point.start.slice(11, 13)) === hour,
  );
  return (match ?? series.prices[0]).eur_per_mwh;
}

export default function PricesPage() {
  const { t, lang } = useLang();
  const router = useRouter();
  const [series, setSeries] = useState<DayAheadPriceSeries | null>(null);
  const [savings, setSavings] = useState(0);
  const [wallbox, setWallbox] = useState<WallboxStatus | null>(null);
  const [text, setText] = useState("");
  const [consented, setConsented] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchPrices()
      .then(setSeries)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
    fetchMonthlyReport(currentMonth(), lang)
      .then((res) => setSavings(res.report.savings_eur))
      .catch(() => setSavings(0));
    fetchWallbox()
      .then(setWallbox)
      .catch(() => setWallbox(null));
  }, [lang]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim() || !consented) return;
    try {
      const created = await startPlan(text.trim(), lang);
      router.push(`/plan?thread=${encodeURIComponent(created.thread_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const values = series ? series.prices.map((p) => p.eur_per_mwh / 10) : [];
  const avg = values.length
    ? values.reduce((sum, v) => sum + v, 0) / values.length
    : 0;
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  const nowCt = series ? currentPoint(series) / 10 : 0;
  const nowClass = series
    ? priceClass(currentPoint(series), avg * 10)
    : "mid";

  return (
    <>
      {series && (
        <section className="panel hero" aria-label={t.heroNow}>
          <div className="hero-main">
            <p className="hero-label">
              {t.heroNow}
              <SourceChip source={series.source} />
            </p>
            <p className={`hero-price tabular ${nowClass}`}>
              {formatCt(nowCt, lang)}
              <span className="muted">/kWh</span>
            </p>
          </div>
          <ul className="hero-stats">
            <li>
              <span className="stat-label">{t.statMin}</span>
              <span className="stat-value tabular">
                {formatCt(min, lang)}
              </span>
            </li>
            <li>
              <span className="stat-label">{t.avg}</span>
              <span className="stat-value tabular">
                {formatCt(avg, lang)}
              </span>
            </li>
            <li>
              <span className="stat-label">{t.statMax}</span>
              <span className="stat-value tabular">
                {formatCt(max, lang)}
              </span>
            </li>
          </ul>
        </section>
      )}

      <section className="panel">
        <p className="muted">{t.tagline}</p>
        <ConsentGate
          text={t.consentPlan}
          storageKey="plan"
          onChange={setConsented}
        >
          {() => (
            <form className="plan-form" onSubmit={submit}>
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={t.planPlaceholder}
                aria-label={t.planButton}
              />
              <button type="submit" disabled={!consented}>
                {t.planButton}
              </button>
            </form>
          )}
        </ConsentGate>
        <p className="muted">{t.planHint}</p>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="panel">
        <h2>{t.today}</h2>
        {!series && !error && <p className="muted">{t.loading}</p>}
        {series && <Heatmap series={series} />}
        {series && (
          <GlassBox
            label={t.avg}
            value={`${formatCt(avg, lang)}/kWh`}
            formula={t.avgFormula}
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
          <div className="wallbox-strip">
            <span
              className={`wallbox-dot${wallbox.charging ? " on" : ""}`}
              aria-hidden="true"
            />
            <p>
              {!wallbox.plugged && t.unplugged}
              {wallbox.plugged &&
                (wallbox.charging
                  ? `${t.charging} ${wallbox.power_kw} kW`
                  : t.idle)}
              {wallbox.plugged &&
                ` · ${wallbox.session_kwh.toFixed(1)} kWh ${t.today.toLowerCase()}`}
            </p>
          </div>
        </section>
      )}
    </>
  );
}
