"use client";

/** Alarms view: flex alarm list plus manual watcher trigger. */

import { useEffect, useState } from "react";
import { fetchAlerts, triggerWatch } from "../../lib/api";
import type { Alert, WatchReport } from "../../lib/flexalarm";
import { useLang } from "../../lib/i18n";

export default function AlarmsPage() {
  const { t, lang } = useLang();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [report, setReport] = useState<WatchReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAlerts()
      .then(setAlerts)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
  }, []);

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

  return (
    <section className="panel">
      <h2>{t.alertsTitle}</h2>
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
            {alert.title} <span className="alert-kind">{alert.kind}</span>
          </h3>
          <p>{alert.body}</p>
          <p className="muted">
            {alert.status} · {alert.reason} · {alert.created_at}
          </p>
        </article>
      ))}
    </section>
  );
}
