"use client";

/** Sign-in view: email form plus magic-link receipt. */

import { useState } from "react";
import { requestLink } from "../../lib/api";
import { useLang } from "../../lib/i18n";
import { useSession } from "../../lib/session";

export default function SignInPage() {
  const { t } = useLang();
  const { me } = useSession();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    setError("");
    if (!email.includes("@")) {
      setError(t.invalidEmail);
      return;
    }
    setBusy(true);
    try {
      const receipt = await requestLink(email.trim());
      setSent(true);
      setDevLink(receipt.dev_link);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>{t.signinTitle}</h2>
      <p className="muted">{t.signinIntro}</p>
      {me && (
        <p className="muted">
          {t.accountEmail}: {me.email}
        </p>
      )}
      {error && <p className="error">{error}</p>}
      {sent ? (
        <>
          <p className="flash">{t.linkSent}</p>
          <p className="muted">{t.linkSentBody}</p>
          {devLink && (
            <p className="muted">
              {t.devLinkNote}{" "}
              <a href={devLink} data-testid="dev-link">
                {t.goSignin}
              </a>
            </p>
          )}
        </>
      ) : (
        <div className="form-row">
          <label>
            {t.emailLabel}{" "}
            <input
              type="email"
              value={email}
              placeholder={t.emailPlaceholder}
              aria-label={t.emailLabel}
              onChange={(event) => setEmail(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") send().catch(() => {});
              }}
            />
          </label>
          <button type="button" disabled={busy} onClick={() => send().catch(() => {})}>
            {t.sendLink}
          </button>
        </div>
      )}
    </section>
  );
}
