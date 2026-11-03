"use client";

/** Live agent trace over server-sent events. */

import { useEffect, useState } from "react";
import { traceUrl } from "../lib/api";
import {
  formatDuration,
  friendlyModel,
  parseTraceLine,
  stepDurationMs,
  type TraceStep,
} from "../lib/trace";
import { useLang } from "../lib/i18n";

export default function TraceStream({ threadId }: { threadId: string }) {
  const { t, lang } = useLang();
  const [lines, setLines] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const source = new EventSource(traceUrl(threadId), {
      withCredentials: true,
    });
    source.onmessage = (event) => {
      const text = String(event.data ?? "");
      if (text === "[done]") {
        setDone(true);
        source.close();
        return;
      }
      setLines((prev) => (prev.includes(text) ? prev : [...prev, text]));
    };
    source.onerror = () => {
      setFailed(true);
      source.close();
    };
    return () => source.close();
  }, [threadId, attempt]);

  const stepLabel: Record<string, string> = {
    perceive: t.pipe1Name,
    analyst: t.pipe2Name,
    scheduler: t.pipe3Name,
    explainer: t.pipe4Name,
    critic: t.pipe5Name,
    approve: t.pipe6Name,
    dispatch: t.traceDispatch,
    publish: t.tracePublish,
  };

  const steps: TraceStep[] = lines.map(
    (line) =>
      parseTraceLine(line) ?? { stamp: "", node: "", model: null, detail: line },
  );

  return (
    <section className="panel" aria-label={t.traceTitle}>
      <h2>{t.traceTitle}</h2>
      <ol className="steps-live">
        {steps.map((step, index) => {
          const current = !done && index === steps.length - 1;
          const previous = index > 0 ? steps[index - 1].stamp : null;
          const duration =
            step.stamp && previous
              ? stepDurationMs(step.stamp, previous)
              : null;
          return (
            <li
              key={`${step.stamp}-${index}`}
              className={current ? "current" : "done"}
            >
              <span className="step-dot" aria-hidden="true">
                {!current && "✓"}
              </span>
              <div className="step-body">
                <p>
                  <strong>{stepLabel[step.node] ?? step.node}</strong>
                  {step.model && (
                    <span className="step-model">
                      {friendlyModel(step.model, lang)}
                    </span>
                  )}
                  {duration !== null && (
                    <span className="step-dur tabular">
                      {formatDuration(duration, lang)}
                    </span>
                  )}
                </p>
                <p className="muted">{step.detail}</p>
              </div>
            </li>
          );
        })}
      </ol>
      {!done && steps.length === 0 && !failed && (
        <p className="muted">{t.runningNote}</p>
      )}
      {failed && !done && (
        <p className="muted">
          {t.traceFailed}{" "}
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setFailed(false);
              setAttempt((value) => value + 1);
            }}
          >
            {t.retryPlan}
          </button>
        </p>
      )}
    </section>
  );
}
