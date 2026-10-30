"use client";

/** Page shell: header with live alarm count, sidebar, footer. */

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Header from "./Header";
import Footer from "./Footer";
import MemorySidebar from "./MemorySidebar";
import { fetchAlerts } from "../lib/api";

export default function Shell({ children }: { children: ReactNode }) {
  const [alarmCount, setAlarmCount] = useState(0);

  useEffect(() => {
    fetchAlerts()
      .then((alerts) => setAlarmCount(alerts.length))
      .catch(() => setAlarmCount(0));
  }, []);

  return (
    <div className="shell">
      <Header alarmCount={alarmCount} />
      <div className="body-row">
        <main className="main">{children}</main>
        <MemorySidebar />
      </div>
      <Footer />
    </div>
  );
}
