"use client";

/** Session state for the Leitstand, loaded once per page. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { fetchMe, setSessionHousehold } from "./api";
import type { SessionInfo } from "./auth";

interface SessionState {
  me: SessionInfo | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionState>({
  me: null,
  loading: true,
  refresh: async () => {},
});

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    await fetchMe()
      .then((session) => {
        setSessionHousehold(session.household_id);
        setMe(session);
      })
      .catch(() => setMe(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    let live = true;
    fetchMe()
      .then((session) => {
        if (!live) return;
        setSessionHousehold(session.household_id);
        setMe(session);
      })
      .catch(() => {
        if (live) setMe(null);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <SessionContext.Provider value={{ me, loading, refresh }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  return useContext(SessionContext);
}
