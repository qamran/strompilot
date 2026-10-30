"use client";

/** Glass-box drawer showing the formula behind one number. */

import { useState } from "react";
import { useLang } from "../lib/i18n";

interface Props {
  label: string;
  value: string;
  formula: string;
  source: string;
}

export default function GlassBox({ label, value, formula, source }: Props) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  return (
    <div className="glassbox">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        {label}: <span className="tabular">{value}</span> [{t.formula}]
      </button>
      {open && (
        <div className="drawer">
          <code>{formula}</code>
          <p className="muted">
            {t.source}: {source}
          </p>
        </div>
      )}
    </div>
  );
}
