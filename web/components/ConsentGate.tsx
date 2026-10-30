"use client";

/** Slim inline consent bar: never blocks the page, remembered per session. */

import { useEffect, useState, type ReactNode } from "react";
import { useLang } from "../lib/i18n";

export default function ConsentGate({
  text,
  storageKey,
  onChange,
  children,
}: {
  text: string;
  storageKey: string;
  onChange?: (agreed: boolean) => void;
  children: () => ReactNode;
}) {
  const { t } = useLang();
  const [agreed, setAgreed] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    Promise.resolve(
      sessionStorage.getItem(`strompilot-consent:${storageKey}`) === "1",
    ).then((stored) => {
      setAgreed(stored);
      onChange?.(stored);
    });
  }, [storageKey, onChange]);

  function confirm() {
    sessionStorage.setItem(`strompilot-consent:${storageKey}`, "1");
    setAgreed(true);
    onChange?.(true);
  }

  return (
    <>
      {!agreed && (
        <div className="consent-bar" role="region" aria-label={t.consentTitle}>
          <label>
            <input
              type="checkbox"
              checked={checked}
              onChange={(event) => setChecked(event.target.checked)}
            />{" "}
            {text}
          </label>
          <button type="button" disabled={!checked} onClick={confirm}>
            {t.consentOk}
          </button>
        </div>
      )}
      {children()}
    </>
  );
}
