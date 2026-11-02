"use client";

/** Page shell: header with palette, sidebar, footer. */

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Header from "./Header";
import Footer from "./Footer";
import MemorySidebar from "./MemorySidebar";
import CommandPalette from "./CommandPalette";
import { fetchAlerts } from "../lib/api";
import { useSession } from "../lib/session";

export default function Shell({ children }: { children: ReactNode }) {
  const { me, loading } = useSession();
  const [alarmCount, setAlarmCount] = useState(0);
  const [palette, setPalette] = useState(false);

  useEffect(() => {
    if (loading || !me) return;
    fetchAlerts()
      .then((alerts) => setAlarmCount(alerts.length))
      .catch(() => setAlarmCount(0));
  }, [loading, me]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPalette((prev) => !prev);
      }
      if (event.key === "Escape") setPalette(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="shell">
      <Header alarmCount={alarmCount} onPalette={() => setPalette(true)} />
      <div className="body-row">
        <main className="main">{children}</main>
        <MemorySidebar />
      </div>
      <Footer />
      {palette && <CommandPalette onClose={() => setPalette(false)} />}
    </div>
  );
}
