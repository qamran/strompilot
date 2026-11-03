"use client";

/** One-line consent state with a link to the household settings. */

import Link from "next/link";
import { useLang } from "../lib/i18n";
import { useSession } from "../lib/session";

export default function ConsentNote() {
  const { t } = useLang();
  const { me } = useSession();
  if (!me) return null;
  return (
    <p className="muted">
      {me.consent_agreed ? t.consentLineAgreed : t.consentLineMissing}{" "}
      <Link href="/household">{t.consentManage}</Link>
    </p>
  );
}
