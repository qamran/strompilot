"use client";

/** Animated savings odometer that ticks toward the target value. */

import { useEffect, useRef, useState } from "react";
import { useLang } from "../lib/i18n";
import { formatEur } from "../lib/format";

export default function Odometer({
  value,
  mood = "positive",
}: {
  value: number;
  mood?: "positive" | "negative";
}) {
  const { lang } = useLang();
  const [shown, setShown] = useState(0);
  const target = useRef(value);

  useEffect(() => {
    target.current = value;
    if (
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      value === 0
    ) {
      Promise.resolve(value).then(setShown);
      return;
    }
    const start = performance.now();
    const from = 0;
    const duration = 1200;
    let alive = true;
    function tick(now: number) {
      if (!alive) return;
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setShown(from + (target.current - from) * eased);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    return () => {
      alive = false;
    };
  }, [value]);

  return (
    <span className={`odometer ${mood}`}>
      <span aria-hidden="true">{formatEur(shown, lang)}</span>
      <span className="sr-only" aria-live="polite">
        {formatEur(value, lang)}
      </span>
    </span>
  );
}
