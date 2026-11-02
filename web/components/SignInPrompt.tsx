"use client";

/** Sign-in prompt shown on household views without a session. */

import Link from "next/link";
import { useLang } from "../lib/i18n";

export default function SignInPrompt() {
  const { t } = useLang();
  return (
    <section className="panel">
      <h2>{t.needSignin}</h2>
      <p className="muted">{t.needSigninBody}</p>
      <p>
        <Link href="/signin" className="button-link">
          {t.goSignin}
        </Link>
      </p>
    </section>
  );
}
