"use client";

/** Today view: plan entry first, then price-now hero, glance, plans, savings. */

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  fetchMonthlyReport,
  fetchPlan,
  fetchPrices,
  fetchWallbox,
  startPlan,
} from "../lib/api";
import { allInCt, type DayAheadPriceSeries } from "../lib/prices";
import {
  cheapestWindow,
  formatCt,
  formatDay,
  formatMonthName,
  priceClass,
  savingsClass,
} from "../lib/format";
import { useLang } from "../lib/i18n";
import { useSession } from "../lib/session";
import Heatmap from "../components/Heatmap";
import Odometer from "../components/Odometer";
import GlassBox from "../components/GlassBox";
import SourceChip from "../components/SourceChip";
import ConsentNote from "../components/ConsentNote";
import type { WallboxStatus } from "../lib/wallbox";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function currentPoint(series: DayAheadPriceSeries): number {
  const hour = new Date().getHours();
  const match = series.prices.find(
    (point) => Number(point.start.slice(11, 13)) === hour,
  );
  return allInCt(match ?? series.prices[0]);
}

export default function Home() {
  const { t, lang } = useLang();
  const { me, loading } = useSession();
  const router = useRouter();
  const agreed = me?.consent_agreed === true;
  const [series, setSeries] = useState<DayAheadPriceSeries | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [savings, setSavings] = useState(0);
  const [reportMonth, setReportMonth] = useState("");
  const [wallbox, setWallbox] = useState<WallboxStatus | null>(null);
  const [lastThread] = useState<string | null>(() => {
    try {
      return typeof window === "undefined"
        ? null
        : window.localStorage.getItem("strompilot-last-thread");
    } catch {
      return null;
    }
  });
  const [lastNote, setLastNote] = useState<string | null>(null);

  useEffect(() => {
    fetchPrices()
      .then(setSeries)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
    fetchWallbox()
      .then(setWallbox)
      .catch(() => setWallbox(null));
  }, [lang]);

  useEffect(() => {
    if (loading || !me) return;
    fetchMonthlyReport(currentMonth(), lang)
      .then((res) => {
        setSavings(res.report.savings_eur);
        setReportMonth(res.report.month);
      })
      .catch(() => setSavings(0));
  }, [lang, loading, me]);

  useEffect(() => {
    if (!me || !lastThread) return;
    fetchPlan(lastThread)
      .then((detail) => {
        const note =
          detail.status === "paused"
            ? t.pausedNote
            : detail.status === "published"
              ? t.publishedNote
              : detail.status === "running"
                ? t.runningNote
                : t.blockedNote;
        setLastNote(note);
      })
      .catch(() => setLastNote(null));
  }, [me, lastThread, t]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim() || !agreed) return;
    try {
      const created = await startPlan(text.trim(), lang);
      router.push(`/plan?thread=${encodeURIComponent(created.thread_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const points = series?.prices ?? [];
  const allIns = points.map(allInCt);
  const avg = allIns.length
    ? allIns.reduce((sum, value) => sum + value, 0) / allIns.length
    : 0;
  const min = allIns.length ? Math.min(...allIns) : 0;
  const max = allIns.length ? Math.max(...allIns) : 0;
  const nowCt = series && points.length > 0 ? currentPoint(series) : 0;
  const nowClass =
    series && points.length > 0
      ? priceClass(series.prices[0].eur_per_mwh, nowCt, allIns)
      : "mid";
  const cheapest = series ? cheapestWindow(points) : null;
  const monthName = reportMonth ? formatMonthName(reportMonth, lang) : "…";
  const [savedBefore, savedAfter] = t.savedSentence.split("{amount}");

  return (
    <>
      <section className="panel">
        <p className="lede">{t.tagline}</p>
        <ConsentNote />
        <form className="plan-form" onSubmit={submit}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t.planPlaceholder}
            aria-label={t.planButton}
          />
          <button type="submit" disabled={!agreed}>
            {t.planButton}
          </button>
        </form>
        <p className="muted">{t.planHint}</p>
      </section>

      {series && (
        <section className="panel hero" aria-label={t.heroNow}>
          <div className="hero-main">
            <p className="hero-label">
              {t.heroNow}
              <SourceChip source={series.source} stale={series.stale} />
            </p>
            <p className={`hero-price tabular ${nowClass}`}>
              {formatCt(nowCt, lang)}
              <span className="muted">/kWh</span>
            </p>
            <div className="hero-stats">
              <div>
                <span className="stat-label">{t.statMin}</span>{" "}
                <span className="stat-value">{formatCt(min, lang)}</span>
              </div>
              <div>
                <span className="stat-label">{t.statMax}</span>{" "}
                <span className="stat-value">{formatCt(max, lang)}</span>
              </div>
            </div>
            {cheapest && (
              <p className="muted">
                {t.cheapestWindow}: {cheapest.start}–{cheapest.end} ·{" "}
                {formatCt(cheapest.avgCt, lang)}
              </p>
            )}
          </div>
        </section>
      )}

      <section className="panel" aria-label={t.todayGlance}>
        <h2>{t.todayGlance}</h2>
        {series && <Heatmap series={series} />}
        {series && (
          <GlassBox
            label={t.heroNow}
            value={`${formatCt(avg, lang)} · ${formatDay(series.date, lang)}`}
            formula={t.avgFormula}
            source={series.source}
          />
        )}
        {wallbox && (
          <p className="muted">
            <span
              className={`wallbox-dot${wallbox.charging ? " on" : ""}`}
              aria-hidden="true"
            />{" "}
            {!wallbox.plugged && t.unplugged}
            {wallbox.plugged &&
              wallbox.charging &&
              `${t.charging} ${wallbox.power_kw} kW`}
            {wallbox.plugged && !wallbox.charging && t.idle}
            {wallbox.plugged &&
              ` · ${wallbox.session_kwh.toFixed(1)} kWh ${t.today.toLowerCase()}`}
          </p>
        )}
      </section>

      {lastThread && (
        <section className="panel" aria-label={t.lastPlan}>
          <h2>{t.lastPlan}</h2>
          {lastNote && <p className="muted">{lastNote}</p>}
          <p>
            <Link href={`/plan?thread=${lastThread}`}>{t.lastPlanOpen}</Link>
          </p>
        </section>
      )}

      <section className="panel" aria-label={t.reportSavings}>
        <h2>{t.reportSavings}</h2>
        {savings > 0 ? (
          <p>
            {savedBefore.replace("{month}", monthName)}
            <Odometer value={savings} mood={savingsClass(savings)} />
            {savedAfter.replace("{month}", monthName)}
          </p>
        ) : (
          <>
            <p className="muted">{t.savingsLoss}</p>
            <p>
              <Link href="/plan">{t.seePlan}</Link>
            </p>
          </>
        )}
      </section>

      {error && <p className="error">{error}</p>}
    </>
  );
}
