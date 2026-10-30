"use client";

/** Fahrplan view: Gantt schedule, approvals, feedback, trace, report. */

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  decideApproval,
  fetchApproval,
  fetchMonthlyReport,
  fetchPlan,
  generateIllustration,
  submitFeedback,
  type FeedbackVerdict,
} from "../../lib/api";
import type { PlanDetail, PlanSlot } from "../../lib/plan";
import type { MonthlyReportResponse } from "../../lib/report";
import { useLang } from "../../lib/i18n";
import { formatCt, formatEur } from "../../lib/format";
import TraceStream from "../../components/TraceStream";
import WhyOverlay from "../../components/WhyOverlay";
import GlassBox from "../../components/GlassBox";

function hourPos(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return ((h + m / 60) / 24) * 100;
}

function Gantt({
  schedule,
  onSelect,
}: {
  schedule: PlanSlot[];
  onSelect: (slot: PlanSlot) => void;
}) {
  const now = new Date();
  const nowPct = ((now.getHours() + now.getMinutes() / 60) / 24) * 100;
  return (
    <div className="gantt">
      {schedule.map((slot) => (
        <div className="gantt-row" key={`${slot.device}-${slot.start}`}>
          <span>{slot.device}</span>
          <div className="gantt-track">
            <span
              className="gantt-now"
              style={{ left: `${nowPct}%` }}
              aria-hidden="true"
            />
            <button
              type="button"
              className="gantt-block"
              style={{
                left: `${hourPos(slot.start)}%`,
                width: `${Math.max(hourPos(slot.end) - hourPos(slot.start), 2)}%`,
              }}
              onClick={() => onSelect(slot)}
              title={`${slot.start}–${slot.end}: ${slot.reason}`}
              aria-label={`${slot.device} ${slot.start}-${slot.end}`}
            />
          </div>
          <span className="tabular">
            {slot.start}–{slot.end}
          </span>
        </div>
      ))}
    </div>
  );
}

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function FahrplanInner() {
  const { t, lang } = useLang();
  const params = useSearchParams();
  const threadId = params.get("thread") ?? "";
  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [approval, setApproval] = useState("");
  const [selected, setSelected] = useState<PlanSlot | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [report, setReport] = useState<MonthlyReportResponse | null>(null);
  const [artBusy, setArtBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!threadId) return;
    try {
      const detail = await fetchPlan(threadId);
      setPlan(detail);
      const status = await fetchApproval(threadId);
      setApproval(status.status);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [threadId]);

  useEffect(() => {
    if (!threadId) return;
    fetchPlan(threadId)
      .then((detail) => {
        setPlan(detail);
        return fetchApproval(threadId);
      })
      .then((status) => {
        setApproval(status.status);
        setError("");
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [load, threadId]);

  useEffect(() => {
    fetchMonthlyReport(currentMonth())
      .then(setReport)
      .catch(() => setReport(null));
  }, []);

  async function decide(approved: boolean) {
    if (!threadId) return;
    await decideApproval(threadId, approved);
    await load();
  }

  async function judge(device: string, verdict: FeedbackVerdict) {
    await submitFeedback(device, verdict);
    setFeedbackMsg(t.feedbackThanks);
  }

  async function makeArt() {
    setArtBusy(true);
    try {
      const art = await generateIllustration(currentMonth());
      setReport((prev) =>
        prev
          ? { report: prev.report, illustration_data_url: art.illustration_data_url }
          : prev,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setArtBusy(false);
    }
  }

  const statusNote =
    approval === "paused"
      ? t.pausedNote
      : approval === "published"
        ? t.publishedNote
        : approval === "blocked"
          ? t.blockedNote
          : t.runningNote;

  return (
    <>
      <section className="panel">
        <h2>{t.navSchedule}</h2>
        {!threadId && <p className="muted">{t.scheduleEmpty}</p>}
        {threadId && !plan && <p className="muted">{t.runningNote}</p>}
        {error && <p className="error">{error}</p>}
        {plan?.schedule && (
          <Gantt schedule={plan.schedule} onSelect={setSelected} />
        )}
        {plan?.narration && <p>{plan.narration}</p>}
        {plan?.total_cost_eur !== null &&
          plan?.total_cost_eur !== undefined && (
            <GlassBox
              label={t.today}
              value={formatEur(plan.total_cost_eur, lang)}
              formula="Σ Energie(kWh) × Preis(ct/kWh) / 100"
              source="aWATTar day-ahead + Strompilot tariff math"
            />
          )}
        <p className="muted">{statusNote}</p>
        <p className="muted">{t.quarterHourNote}</p>
        {plan?.error && <p className="error">{plan.error}</p>}
      </section>

      {approval === "paused" && (
        <section className="panel">
          <div className="feedback-row">
            <button type="button" onClick={() => decide(true)}>
              {t.approve}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => decide(false)}
            >
              {t.reject}
            </button>
          </div>
        </section>
      )}

      {plan?.schedule && (
        <section className="panel">
          <h2>{t.feedbackTitle}</h2>
          {plan.schedule.map((slot) => (
            <div
              className="feedback-row"
              key={`${slot.device}-${slot.start}-fb`}
            >
              <span>{slot.device}</span>
              <button
                type="button"
                className="secondary"
                onClick={() => judge(slot.device, "too_early")}
              >
                {t.feedbackEarly}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => judge(slot.device, "good")}
              >
                {t.feedbackGood}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => judge(slot.device, "too_late")}
              >
                {t.feedbackLate}
              </button>
            </div>
          ))}
          {feedbackMsg && <p className="muted">{feedbackMsg}</p>}
        </section>
      )}

      {threadId && <TraceStream threadId={threadId} />}

      <section className="panel">
        <h2>{t.reportTitle}</h2>
        {report && (
          <>
            <p>
              {t.reportSavings}:{" "}
              <strong className="tabular">
                {formatEur(report.report.savings_eur, lang)}
              </strong>
            </p>
            {report.report.worst_hour && (
              <GlassBox
                label={t.worstHour}
                value={`${report.report.worst_hour.day} ${report.report.worst_hour.hour}:00 · ${formatCt(report.report.worst_hour.price_ct_kwh, lang)}`}
                formula="max(Preis(h)) über alle Monatstage"
                source="aWATTar day-ahead Archiv/Sample"
              />
            )}
            {report.illustration_data_url ? (
              // Data-URL art from the report cache: no optimizer benefit.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className="report-art"
                src={report.illustration_data_url}
                alt={t.reportArtCached}
              />
            ) : (
              <button
                type="button"
                className="secondary"
                disabled={artBusy}
                onClick={makeArt}
              >
                {t.reportArt}
              </button>
            )}
          </>
        )}
      </section>

      {selected && (
        <WhyOverlay
          slot={selected}
          citations={plan?.citations ?? []}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}

export default function FahrplanPage() {
  return (
    <Suspense>
      <FahrplanInner />
    </Suspense>
  );
}
