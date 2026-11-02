"use client";

/** Magic-link landing: verifies the token, then opens the account. */

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setSessionHousehold, verifyLink } from "../../../lib/api";
import { useLang } from "../../../lib/i18n";
import { useSession } from "../../../lib/session";

function VerifyInner() {
  const { t } = useLang();
  const { refresh } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!token) {
      return;
    }
    let live = true;
    verifyLink(token)
      .then((session) => {
        setSessionHousehold(session.household_id);
        return refresh();
      })
      .then(() => {
        if (live) router.replace("/account");
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [token, refresh, router]);

  const showFailed = failed || !token;
  return (
    <section className="panel">
      <h2>{t.verifyTitle}</h2>
      {showFailed ? (
        <p className="error">{t.verifyFailed}</p>
      ) : (
        <p className="muted">{t.verifyWorking}</p>
      )}
    </section>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
