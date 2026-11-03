"use client";

/** Small Ask-Why box: tariff-guide answers with cited sources. */

import { useState, type FormEvent } from "react";
import { askWhy } from "../lib/api";
import type { AskAnswer } from "../lib/ask";
import { useLang } from "../lib/i18n";
import { friendlyModel } from "../lib/trace";

export default function AskWhy() {
  const { t, lang } = useLang();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      setAnswer(await askWhy(question.trim(), lang));
    } catch (err) {
      setAnswer(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-label={t.askTitle}>
      <h2>{t.askTitle}</h2>
      <form className="plan-form" onSubmit={submit}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t.askPlaceholder}
          aria-label={t.askTitle}
          maxLength={500}
        />
        <button type="submit" disabled={busy || !question.trim()}>
          {t.askButton}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {answer && (
        <>
          <p>{answer.answer}</p>
          {answer.citations.length > 0 && (
            <ul>
              {answer.citations.map((citation) => (
                <li key={citation.source_url}>
                  <a
                    href={citation.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {citation.title} · {citation.source_name}
                  </a>
                </li>
              ))}
            </ul>
          )}
          <p className="muted">{friendlyModel(answer.model, lang)}</p>
        </>
      )}
    </section>
  );
}
