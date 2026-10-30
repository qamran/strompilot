"use client";

/** Consent dialog: modal with checkbox plus OK, remembered per session. */

import { useEffect, useState, type ReactNode } from "react";
import { useLang } from "../lib/i18n";

export default function ConsentGate({
  text,
  storageKey,
  children,
}: {
  text: string;
  storageKey: string;
  children: () => ReactNode;
}) {
  const { t } = useLang();
  const [agreed, setAgreed] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    Promise.resolve(
      sessionStorage.getItem(`strompilot-consent:${storageKey}`) === "1",
    ).then(setAgreed);
  }, [storageKey]);

  function confirm() {
    sessionStorage.setItem(`strompilot-consent:${storageKey}`, "1");
    setAgreed(true);
  }

  if (agreed) return <>{children()}</>;
  return (
    <div className="overlay" role="dialog" aria-label={t.consentTitle}>
      <div className="overlay-card consent">
        <h2>{t.consentTitle}</h2>
        <p>{text}</p>
        <label>
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
          />{" "}
          {text}
        </label>
        <p>
          <button type="button" disabled={!checked} onClick={confirm}>
            {t.consentOk}
          </button>
        </p>
      </div>
    </div>
  );
}
