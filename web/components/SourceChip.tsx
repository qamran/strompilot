"use client";

/** Small source label carried by every number. */

import { useLang } from "../lib/i18n";

export default function SourceChip({ source }: { source: string }) {
  const { t } = useLang();
  const badge =
    source === "sample"
      ? t.sampleBadge
      : source === "live"
        ? t.liveBadge
        : t.cachedBadge;
  return (
    <span className="source-chip" title={`${t.source}: ${source}`}>
      {badge}
    </span>
  );
}
