"use client";

/** Account view: profile, local migration, sign-out. */

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  isAuthError,
  migrateHousehold,
  signOut,
} from "../../lib/api";
import { useLang } from "../../lib/i18n";
import { useSession } from "../../lib/session";
import SignInPrompt from "../../components/SignInPrompt";

export default function AccountPage() {
  const { t, lang } = useLang();
  const { me, loading, refresh } = useSession();
  const router = useRouter();
  const [source, setSource] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  if (loading) {
    return (
      <section className="panel">
        <p className="muted">{t.loading}</p>
      </section>
    );
  }
  if (!me) {
    return <SignInPrompt />;
  }

  async function adopt() {
    setError("");
    setNote("");
    try {
      const receipt = await migrateHousehold(
        source.trim() || "demo-haushalt",
      );
      const total = Object.values(receipt.migrated).reduce(
        (sum, count) => sum + count,
        0,
      );
      setNote(`${t.migratedNote} (${total})`);
      window.dispatchEvent(new Event("strompilot:memory"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function leave() {
    setError("");
    try {
      await signOut();
      await refresh();
      router.replace("/");
    } catch (err) {
      if (!isAuthError(err)) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }
  }

  return (
    <>
      <section className="panel">
        <h2>{t.accountTitle}</h2>
        {note && <p className="flash">{note}</p>}
        {error && <p className="error">{error}</p>}
        <ul>
          <li className="memory-row">
            <span className="muted">{t.accountEmail}</span>
            <span>{me.email}</span>
          </li>
          <li className="memory-row">
            <span className="muted">{t.accountExpiry}</span>
            <span>
              {new Date(me.expires_at).toLocaleString(
                lang === "de" ? "de-DE" : "en-GB",
                {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                },
              )}
            </span>
          </li>
        </ul>
        <div className="form-row">
          <button type="button" onClick={() => leave().catch(() => {})}>
            {t.signOut}
          </button>
        </div>
      </section>
      <section className="panel" aria-label={t.migrateTitle}>
        <h2>{t.migrateTitle}</h2>
        <p className="muted">{t.migrateBody}</p>
        <div className="form-row">
          <input
            type="text"
            value={source}
            placeholder={t.migratePlaceholder}
            aria-label={t.migrateTitle}
            onChange={(event) => setSource(event.target.value)}
          />
          <button type="button" onClick={() => adopt().catch(() => {})}>
            {t.migrateButton}
          </button>
        </div>
      </section>
    </>
  );
}
