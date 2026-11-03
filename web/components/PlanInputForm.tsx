"use client";

/** Shared sentence input for first plans and failed-run retries. */

import type { FormEvent } from "react";

export default function PlanInputForm({
  text,
  onText,
  onSubmit,
  submitLabel,
  placeholder,
  disabled,
}: {
  text: string;
  onText: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  submitLabel: string;
  placeholder: string;
  disabled: boolean;
}) {
  return (
    <form className="plan-form" onSubmit={onSubmit}>
      <input
        value={text}
        onChange={(e) => onText(e.target.value)}
        placeholder={placeholder}
        aria-label={submitLabel}
      />
      <button type="submit" disabled={disabled}>
        {submitLabel}
      </button>
    </form>
  );
}
