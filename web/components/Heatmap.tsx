"use client";

/** Canvas heatmap: luminous price day with axis, now-line, hover readout. */

import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { allInCt, type DayAheadPriceSeries } from "../lib/prices";
import { cheapestWindow, formatCt, priceClass } from "../lib/format";
import { useLang } from "../lib/i18n";

const COLORS: Record<string, string> = {
  negative: "#46dcff",
  cheap: "#3ddc84",
  mid: "#ffb224",
  spike: "#ff5d5d",
};

const AXIS_HOURS = [0, 6, 12, 18, 24];

export default function Heatmap({ series }: { series: DayAheadPriceSeries }) {
  const { t, lang } = useLang();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const prices = series.prices;
    if (prices.length === 0) return;
    const allIns = prices.map(allInCt);
    const cheap = cheapestWindow(prices);
    const cheapStart = cheap
      ? prices.findIndex((p) => p.start.slice(11, 16) === cheap.start)
      : -1;
    const cheapEnd = cheap
      ? prices.findIndex((p) => p.end.slice(11, 16) === cheap.end)
      : -1;
    const width = canvas.width;
    const height = canvas.height;
    const axisPad = 22;
    const plotH = height - axisPad;
    const barWidth = width / prices.length;
    const max = Math.max(...prices.map((p) => Math.abs(p.eur_per_mwh)), 1);
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    let frame = 0;
    let alive = true;

    function draw() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, width, height);
      prices.forEach((point, index) => {
        const cls = priceClass(point.eur_per_mwh, allIns[index], allIns);
        const barHeight = (Math.abs(point.eur_per_mwh) / max) * (plotH - 16);
        const x = index * barWidth + 1;
        const w = Math.max(barWidth - 2, 1);
        ctx.fillStyle = COLORS[cls];
        if (cls === "negative" && !reduced) {
          ctx.globalAlpha = 0.55 + 0.45 * Math.abs(Math.sin(frame / 12));
        } else {
          ctx.globalAlpha = cls === "negative" ? 1 : 0.92;
        }
        if (point.eur_per_mwh >= 0) {
          ctx.fillRect(x, plotH - 6 - barHeight, w, barHeight);
        } else {
          ctx.fillRect(x, 6, w, barHeight);
        }
        ctx.globalAlpha = 1;
      });
      if (cheap && cheapStart >= 0 && cheapEnd >= cheapStart) {
        const x0 = cheapStart * barWidth + 1;
        const x1 = (cheapEnd + 1) * barWidth - 1;
        ctx.strokeStyle = COLORS.cheap;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x0, 3);
        ctx.lineTo(x1, 3);
        ctx.moveTo(x0, 3);
        ctx.lineTo(x0, 9);
        ctx.moveTo(x1, 3);
        ctx.lineTo(x1, 9);
        ctx.stroke();
        ctx.fillStyle = COLORS.cheap;
        ctx.font = "11px JetBrains Mono, monospace";
        ctx.textAlign = "center";
        const label = `${cheap.start}–${cheap.end} · ${formatCt(cheap.avgCt, lang)}`;
        ctx.fillText(label, (x0 + x1) / 2, 22);
      }
      ctx.fillStyle = "#61738d";
      ctx.font = "11px JetBrains Mono, monospace";
      ctx.textAlign = "center";
      AXIS_HOURS.forEach((hour) => {
        const x = Math.min(Math.max((hour / 24) * width, 14), width - 14);
        ctx.fillText(`${String(hour).padStart(2, "0")}:00`, x, height - 6);
      });
      const now = new Date();
      const nx = ((now.getHours() + now.getMinutes() / 60) / 24) * width;
      ctx.strokeStyle = "#e9eff8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(nx, 0);
      ctx.lineTo(nx, plotH);
      ctx.stroke();
      frame += 1;
      if (alive && !reduced) requestAnimationFrame(draw);
    }
    draw();
    return () => {
      alive = false;
    };
  }, [series, lang]);

  function onMove(event: ReactMouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas || series.prices.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const index = Math.floor(
      ((event.clientX - rect.left) / rect.width) * series.prices.length,
    );
    const point = series.prices[Math.min(Math.max(index, 0), 23)];
    if (!point) return;
    const start = point.start.slice(11, 16);
    setHover(`${start} · ${formatCt(allInCt(point), lang)}/kWh`);
  }

  const legend: Array<[string, string]> = [
    [COLORS.negative, t.legendNegative],
    [COLORS.cheap, t.legendCheap],
    [COLORS.mid, t.legendMid],
    [COLORS.spike, t.legendSpike],
  ];

  return (
    <div className="heatmap-wrap">
      <canvas
        ref={canvasRef}
        width={720}
        height={180}
        className="heatmap"
        role="img"
        aria-label={`${t.today} ${series.date}`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      />
      {hover && <p className="heatmap-readout tabular">{hover}</p>}
      <ul className="heatmap-legend">
        {legend.map(([color, label]) => (
          <li key={label}>
            <i style={{ background: color }} />
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
}
