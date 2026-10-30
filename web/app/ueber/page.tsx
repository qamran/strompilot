"use client";

/** Über view: disclaimers, attribution, privacy, models. */

import { useLang } from "../../lib/i18n";
import { CONTRACT_VERSION } from "../../lib/contract";

export default function AboutPage() {
  const { t } = useLang();
  return (
    <>
      <section className="panel">
        <h2>{t.aboutTitle}</h2>
        <p>{t.tagline}</p>
        <p className="muted">Contract {CONTRACT_VERSION}</p>
      </section>
      <section className="panel">
        <h2>{t.privacyTitle}</h2>
        <p>{t.privacyBody}</p>
      </section>
      <section className="panel">
        <h2>{t.modelsTitle}</h2>
        <p>{t.modelsBody}</p>
      </section>
      <section className="panel">
        <h2>{t.source}</h2>
        <p>
          {t.smardCredit} · {t.awattarCredit} · {t.bdewCredit}
        </p>
        <p className="muted">{t.disclaimerFooter}</p>
        <p className="muted">
          {t.estimateLabel} · {t.quarterHourNote}
        </p>
      </section>
    </>
  );
}
