"use client";

/** Alarms view: flex alarm list plus manual watcher trigger. */

import { useEffect, useState } from "react";
import { fetchAlerts, triggerWatch } from "../../lib/api";
import type { Alert, WatchReport } from "../../lib/flexalarm";
import { useLang } from "../../lib/i18n";
import { useSession } from "../../lib/session";
import SignInPrompt from "../../components/SignInPrompt";

export default function AlarmsPage() {
  const { t, lang } = useLang();
  const { me, loading } = useSession();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [report, setReport] = useState<WatchReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const kindLabel: Record<string, string> = {
    cheap_window: t.alertCheap,
    price_spike: t.alertSpike,
    negative_prices: t.alertNegative,
  };
  const statusLabel: Record<string, string> = {
    delivered: t.alertDelivered,
    held: t.alertHeld,
    failed: t.alertFailed,
  };
  const channelLabel: Record<string, string> = { log: "Log" };

  function stamp(iso: string): string {
    return new Date(iso).toLocaleString(lang === "de" ? "de-DE" : "en-GB", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  useEffect(() => {
    if (loading || !me) return;
    fetchAlerts()
      .then(setAlerts)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
  }, [loading, me]);

  async function reload() {
    try {
      setAlerts(await fetchAlerts());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function watch() {
    setBusy(true);
    try {
      setReport(await triggerWatch(lang));
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!loading && !me) {
    return <SignInPrompt />;
  }

  return (
    <section className="panel">
      <h2>{t.alertsTitle}</h2>
      <p className="muted">{t.allInNote}</p>
      <button type="button" disabled={busy} onClick={watch}>
        {t.watchNow}
      </button>
      {error && <p className="error">{error}</p>}
      {report && (
        <p className="muted tabular">
          {report.day}: {report.candidates} → {report.fired} ✓ · {report.held}{" "}
          ⏸ · {report.duplicates} ⧉
        </p>
      )}
      {alerts.length === 0 && <p className="muted">{t.noAlerts}</p>}
      {alerts.map((alert) => (
        <article className="alert-card" key={alert.id}>
          <h3>
            <span
              className={`alert-dot ${["cheap", "spike", "negative"].includes(alert.kind) ? alert.kind : "info"}`}
              aria-hidden="true"
            />
            {alert.title}{" "}
            <span className="alert-kind">
              {kindLabel[alert.kind] ?? alert.kind}
            </span>
          </h3>
          <p>{alert.body}</p>
          <p className="muted">
            {statusLabel[alert.status] ?? alert.status} · {alert.reason} ·{" "}
            {stamp(alert.created_at)}
          </p>
          {alert.status === "delivered" && alert.channel && (
            <p className="muted">
              {t.deliveredVia} {channelLabel[alert.channel] ?? alert.channel}
              {alert.delivered_at && ` · ${stamp(alert.delivered_at)}`}
            </p>
          )}
          {alert.status === "failed" && (
            <p className="error">
              {t.deliveryFailed}
              {alert.last_error && `: ${alert.last_error}`}
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
