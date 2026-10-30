"use client";

/** Consent gate shown before any photo or AI use. */

import { useState, type ReactNode } from "react";
import { useLang } from "../lib/i18n";

export default function ConsentGate({
  text,
  children,
}: {
  text: string;
  children: () => ReactNode;
}) {
  const { t } = useLang();
  const [agreed, setAgreed] = useState(false);

  if (agreed) return <>{children()}</>;
  return (
    <section className="panel consent" aria-label={t.consentTitle}>
      <h2>{t.consentTitle}</h2>
      <p>{text}</p>
      <label>
        <input
          type="checkbox"
          checked={agreed}
          onChange={(event) => setAgreed(event.target.checked)}
        />{" "}
        {text}
      </label>
    </section>
  );
}
