"use client";

/** Plan view: Gantt schedule, approvals, feedback, trace, report. */

import { Suspense, useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  decideApproval,
  fetchApproval,
  fetchMonthlyReport,
  fetchPlan,
  fetchPreferences,
  startPlan,
  submitFeedback,
  type FeedbackVerdict,
} from "../../lib/api";
import type { PlanDetail, PlanPriceBar, PlanSlot } from "../../lib/plan";
import { parseQuietRange, type QuietRange } from "../../lib/quiet";
import type { MonthlyReportResponse } from "../../lib/report";
import { friendlyModel } from "../../lib/trace";
import { useLang } from "../../lib/i18n";
import { useSession } from "../../lib/session";
import {
  formatCt,
  formatDay,
  formatDeviceName,
  formatEur,
  priceClass,
  savingsClass,
} from "../../lib/format";
import AskWhy from "../../components/AskWhy";
import ConsentNote from "../../components/ConsentNote";
import PlanInputForm from "../../components/PlanInputForm";
import SignInPrompt from "../../components/SignInPrompt";
import SourceChip from "../../components/SourceChip";
import TraceStream from "../../components/TraceStream";
import WhyOverlay from "../../components/WhyOverlay";
import GlassBox from "../../components/GlassBox";

function hourPos(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return ((h + m / 60) / 24) * 100;
}

function splitQuiet(quiet: QuietRange): Array<{ from: number; to: number }> {
  const from = hourPos(quiet.start);
  const to = hourPos(quiet.end);
  if (from < to) return [{ from, to }];
  return [
    { from, to: 100 },
    { from: 0, to },
  ];
}

function Gantt({
  schedule,
  prices,
  quiet,
  showNow,
  onSelect,
}: {
  schedule: PlanSlot[];
  prices: PlanPriceBar[] | null;
  quiet: QuietRange | null;
  showNow: boolean;
  onSelect: (slot: PlanSlot) => void;
}) {
  const { t, lang } = useLang();
  const now = new Date();
  const nowPct = ((now.getHours() + now.getMinutes() / 60) / 24) * 100;
  const peers = prices ? prices.map((bar) => bar.price_ct_kwh) : [];
  const shadeByHour = new Map(
    (prices ?? []).map((bar) => [
      bar.hour,
      priceClass(1, bar.price_ct_kwh, peers),
    ]),
  );
  const quietRanges = quiet ? splitQuiet(quiet) : [];
  return (
    <div className="gantt">
      <div className="gantt-row" aria-hidden="true">
        <span />
        <div className="gantt-ticks">
          {[0, 6, 12, 18, 24].map((hour) => (
            <span key={hour} style={{ left: `${(hour / 24) * 100}%` }}>
              {String(hour).padStart(2, "0")}:00
            </span>
          ))}
        </div>
        <span />
      </div>
      {schedule.map((slot) => {
        const label = formatDeviceName(slot.device, lang);
        const startPct = hourPos(slot.start);
        const rawEnd = hourPos(slot.end);
        const endPct = rawEnd <= startPct ? 100 : rawEnd;
        return (
          <div className="gantt-row" key={`${slot.device}-${slot.start}`}>
            <span>{label}</span>
            <div className="gantt-track">
              <div className="gantt-cells" aria-hidden="true">
                {Array.from({ length: 24 }, (_, hour) => (
                  <span
                    key={hour}
                    className={`gantt-cell ${shadeByHour.get(hour) ?? ""}`}
                  />
                ))}
              </div>
              {quietRanges.map((range, index) => (
                <span
                  key={index}
                  className="gantt-quiet"
                  style={{
                    left: `${range.from}%`,
                    width: `${range.to - range.from}%`,
                  }}
                  aria-hidden="true"
                />
              ))}
              <button
                type="button"
                className="gantt-block"
                style={{
                  left: `${startPct}%`,
                  width: `${Math.max(endPct - startPct, 2)}%`,
                }}
                onClick={() => onSelect(slot)}
                title={`${slot.start}–${slot.end}: ${slot.reason}`}
                aria-label={`${label} ${slot.start}-${slot.end}`}
              >
                <span className="gantt-label">
                  {label}
                  {slot.cost_eur !== undefined &&
                    ` · ${formatEur(slot.cost_eur, lang)}`}
                </span>
              </button>
              {showNow && (
                <span
                  className="gantt-now"
                  style={{ left: `${nowPct}%` }}
                  aria-hidden="true"
                />
              )}
            </div>
            <span className="tabular">
              {slot.start}–{slot.end}
            </span>
          </div>
        );
      })}
      {quiet && (
        <p className="muted gantt-quiet-note">
          {t.quietTitle} {quiet.start}–{quiet.end}
        </p>
      )}
    </div>
  );
}

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

type Phase = "empty" | "running" | "waiting" | "approved" | "failed";

function PlanInner() {
  const { t, lang } = useLang();
  const { me, loading } = useSession();
  const params = useSearchParams();
  const router = useRouter();
  const threadId = params.get("thread") ?? "";
  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [approval, setApproval] = useState("");
  const [selected, setSelected] = useState<PlanSlot | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [report, setReport] = useState<MonthlyReportResponse | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const agreed = me?.consent_agreed === true;

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
    if (!threadId || loading || !me) return;
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
  }, [load, threadId, loading, me]);

  const [quiet, setQuiet] = useState<QuietRange | null>(null);

  useEffect(() => {
    if (loading || !me) return;
    fetchMonthlyReport(currentMonth(), lang)
      .then(setReport)
      .catch(() => setReport(null));
    fetchPreferences()
      .then((prefs) =>
        setQuiet(parseQuietRange(prefs.preferences["quiet_hours"])),
      )
      .catch(() => setQuiet(null));
  }, [lang, loading, me]);

  async function submitPlan(event: FormEvent) {
    event.preventDefault();
    if (!text.trim() || !agreed) return;
    try {
      const created = await startPlan(text.trim(), lang);
      router.push(`/plan?thread=${encodeURIComponent(created.thread_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function decide(approved: boolean) {
    if (!threadId) return;
    await decideApproval(threadId, approved);
    await load();
  }

  async function judge(device: string, verdict: FeedbackVerdict) {
    await submitFeedback(device, verdict);
    setFeedbackMsg(t.feedbackThanks);
    window.dispatchEvent(new Event("strompilot:memory"));
  }

  useEffect(() => {
    if (!threadId) return;
    try {
      localStorage.setItem("strompilot-last-thread", threadId);
    } catch {
      // Private mode: the last-plan shortcut simply stays empty.
    }
  }, [threadId]);

  const phase: Phase = !threadId
    ? "empty"
    : plan?.error || (error && !plan)
      ? "failed"
      : approval === "paused"
        ? "waiting"
        : approval === "published"
          ? "approved"
          : approval === "blocked" || approval === "done"
            ? "failed"
            : "running";
  const phaseNote =
    phase === "waiting"
      ? t.pausedNote
      : phase === "approved"
        ? t.publishedNote
        : phase === "failed"
          ? t.blockedNote
          : t.runningNote;

  if (!loading && !me) {
    return <SignInPrompt />;
  }

  const planDayLabel = plan?.plan_day ? formatDay(plan.plan_day, lang) : "";
  const todayKey = (() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  })();
  const attribution = plan?.attribution ?? {};
  const attributionBlocks: Array<[string, string]> = [
    ["constraints", t.pipe2Name],
    ["schedule", t.pipe3Name],
    ["narration", t.pipe4Name],
    ["verdict", t.pipe5Name],
  ];

  return (
    <>
      <section className="panel">
        <h2>{t.navSchedule}</h2>
        {(plan?.plan_day || plan?.price_source) && (
          <p className="muted">
            {plan?.plan_day && `${t.planDay}: ${planDayLabel}`}
            {plan?.price_source && (
              <SourceChip
                source={plan.price_source}
                stale={plan.price_stale}
              />
            )}
          </p>
        )}
        {(phase === "empty" || phase === "failed") && <ConsentNote />}
        {phase === "empty" && (
          <PlanInputForm
            text={text}
            onText={setText}
            onSubmit={submitPlan}
            submitLabel={t.planButton}
            placeholder={t.planPlaceholder}
            disabled={!agreed}
          />
        )}
        {phase === "empty" && <p className="muted">{t.planHint}</p>}
        {phase === "failed" && (
          <>
            <p className="muted">{t.retryHint}</p>
            <PlanInputForm
              text={text}
              onText={setText}
              onSubmit={submitPlan}
              submitLabel={t.retryPlan}
              placeholder={t.planPlaceholder}
              disabled={!agreed}
            />
          </>
        )}
        {error && <p className="error">{error}</p>}
        {plan?.schedule && (
          <Gantt
            schedule={plan.schedule}
            prices={plan.prices}
            quiet={quiet}
            showNow={plan.plan_day === todayKey}
            onSelect={setSelected}
          />
        )}
        {plan?.narration && <p>{plan.narration}</p>}
        {plan?.total_cost_eur !== null &&
          plan?.total_cost_eur !== undefined && (
            <GlassBox
              label={t.today}
              value={formatEur(plan.total_cost_eur, lang)}
              formula={t.totalFormula}
              source={t.tariffSource}
            />
          )}
        {Object.keys(attribution).length > 0 && (
          <div className="attribution">
            <span className="muted">{t.glassBoxTitle}</span>
            {attributionBlocks.map(
              ([block, label]) =>
                attribution[block] && (
                  <span key={block} className="attr-chip">
                    {label} · {friendlyModel(attribution[block], lang)}
                  </span>
                ),
            )}
          </div>
        )}
        {phase !== "empty" && (
          <p className="muted" role="status">
            {phaseNote}
          </p>
        )}
        {plan?.error && <p className="error">{plan.error}</p>}
        {approval === "paused" && (
          <div className="approve-bar">
            {plan?.total_cost_eur !== null &&
              plan?.total_cost_eur !== undefined && (
                <span className="tabular">
                  {formatEur(plan.total_cost_eur, lang)}
                </span>
              )}
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
        )}
      </section>

      {plan?.schedule && (
        <section className="panel">
          <h2>{t.feedbackTitle}</h2>
          {plan.schedule.map((slot) => (
            <div
              className="feedback-row"
              key={`${slot.device}-${slot.start}-fb`}
            >
              <span>{formatDeviceName(slot.device, lang)}</span>
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

      {threadId && (
        <TraceStream
          key={`${threadId}:${approval}`}
          threadId={threadId}
        />
      )}

      <AskWhy />

      <section className="panel" id="report">
        <h2>{t.reportTitle}</h2>
        {report && (
          <>
            <p>
              {t.reportSavings}:{" "}
              <strong
                className={`tabular savings ${savingsClass(report.report.savings_eur)}`}
              >
                {formatEur(report.report.savings_eur, lang)}
              </strong>
            </p>
            {report.report.sample_days > 0 && (
              <p className="muted">
                {t.reportSampleDays}: {report.report.sample_days}/
                {report.report.days.length}
              </p>
            )}
            {report.report.worst_hour && (
              <GlassBox
                label={t.worstHour}
                value={`${formatDay(report.report.worst_hour.day, lang)} ${report.report.worst_hour.hour}:00 · ${formatCt(report.report.worst_hour.price_ct_kwh, lang)}`}
                formula={t.worstFormula}
                source={t.archiveSource}
              />
            )}
          </>
        )}
      </section>

      {selected && (
        <WhyOverlay
          slot={selected}
          citations={plan?.citations ?? []}
          attribution={plan?.attribution ?? {}}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}

export default function PlanPage() {
  return (
    <Suspense>
      <PlanInner />
    </Suspense>
  );
}
