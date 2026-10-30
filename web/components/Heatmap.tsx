"use client";

/** Canvas heatmap of one price day with a now-line and pulsing negatives. */

import { useEffect, useRef } from "react";
import type { DayAheadPriceSeries } from "../lib/prices";
import { priceClass } from "../lib/format";

const COLORS: Record<string, string> = {
  negative: "#22d3ee",
  cheap: "#4ade80",
  mid: "#fbbf24",
  spike: "#f87171",
};

export default function Heatmap({ series }: { series: DayAheadPriceSeries }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const prices = series.prices;
    if (prices.length === 0) return;
    const avg =
      prices.reduce((sum, point) => sum + point.eur_per_mwh, 0) / prices.length;
    const width = canvas.width;
    const height = canvas.height;
    const barWidth = width / prices.length;
    const max = Math.max(...prices.map((p) => Math.abs(p.eur_per_mwh)), 1);
    let frame = 0;
    let alive = true;

    function draw() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, width, height);
      prices.forEach((point, index) => {
        const cls = priceClass(point.eur_per_mwh, avg);
        const barHeight = (Math.abs(point.eur_per_mwh) / max) * (height - 20);
        const x = index * barWidth + 1;
        const w = Math.max(barWidth - 2, 1);
        ctx.fillStyle = COLORS[cls];
        if (cls === "negative") {
          ctx.globalAlpha = 0.55 + 0.45 * Math.abs(Math.sin(frame / 12));
        } else {
          ctx.globalAlpha = 1;
        }
        if (point.eur_per_mwh >= 0) {
          ctx.fillRect(x, height - 10 - barHeight, w, barHeight);
        } else {
          ctx.fillRect(x, 10, w, barHeight);
        }
        ctx.globalAlpha = 1;
      });
      const now = new Date();
      const hour = now.getHours() + now.getMinutes() / 60;
      const nx = (hour / 24) * width;
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(nx, 0);
      ctx.lineTo(nx, height);
      ctx.stroke();
      frame += 1;
      if (alive) requestAnimationFrame(draw);
    }
    draw();
    return () => {
      alive = false;
    };
  }, [series]);

  return (
    <canvas
      ref={canvasRef}
      width={720}
      height={160}
      className="heatmap"
      role="img"
      aria-label={`Preise ${series.date}`}
    />
  );
}
