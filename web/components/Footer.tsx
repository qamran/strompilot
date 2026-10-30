"use client";

/** Footer with disclaimers and attribution. */

import { useLang } from "../lib/i18n";

export default function Footer() {
  const { t } = useLang();
  return (
    <footer className="footer">
      <p>{t.disclaimerFooter}</p>
      <p className="muted">
        {t.estimateLabel} · {t.quarterHourNote}
      </p>
      <p className="muted">
        {t.source}: {t.smardCredit} · {t.awattarCredit} · {t.bdewCredit}
      </p>
    </footer>
  );
}
