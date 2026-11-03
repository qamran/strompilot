"use client";

/** Small source label carried by every number. */

import { useLang } from "../lib/i18n";

export default function SourceChip({
  source,
  stale = false,
}: {
  source: string;
  stale?: boolean;
}) {
  const { t } = useLang();
  const kind =
    source === "sample"
      ? "sample"
      : stale
        ? "stale"
        : source.endsWith("-live")
          ? "live"
          : "stale";
  const badge =
    kind === "sample"
      ? t.sampleBadge
      : kind === "live"
        ? t.liveBadge
        : t.cachedBadge;
  return (
    <span className={`source-chip ${kind}`} title={`${t.source}: ${source}`}>
      {badge}
    </span>
  );
}
