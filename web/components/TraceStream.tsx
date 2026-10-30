"use client";

/** Live agent trace over server-sent events. */

import { useEffect, useState } from "react";
import { traceUrl } from "../lib/api";
import { useLang } from "../lib/i18n";

export default function TraceStream({ threadId }: { threadId: string }) {
  const { t } = useLang();
  const [lines, setLines] = useState<string[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const source = new EventSource(traceUrl(threadId));
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
      setDone(true);
      source.close();
    };
    return () => source.close();
  }, [threadId]);

  return (
    <section className="panel" aria-label={t.traceTitle}>
      <h2>{t.traceTitle}</h2>
      <ol className="trace">
        {lines.map((line) => (
          <li key={line}>
            <code>{line}</code>
          </li>
        ))}
      </ol>
      {!done && <p className="muted">{t.runningNote}</p>}
    </section>
  );
}
