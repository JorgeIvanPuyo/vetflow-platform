"use client";

import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useRef,
} from "react";

import { applyStoredActingTenant } from "@/lib/acting-tenant";
import { useAuth } from "./auth-context";
import { validateSession, type SessionStatus } from "./session-bootstrap";
import { SessionStatusScreen } from "./components/session-status-screen";
import { getCurrentUser } from "@/services/auth";
import type { AppRole, CurrentUser } from "@/types/api";

type CurrentUserContextValue = {
  currentUser: CurrentUser | null;
  role: AppRole | null;
  isLoading: boolean;
  errorMessage: string | null;
  refresh: () => Promise<void>;
};

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  // Runs once, during this component's first render — guaranteed to happen before
  // any effect in this tree (including ClinicProvider's own fetch) can fire, so the
  // very first request already carries any stored tenant override.
  useState(() => {
    applyStoredActingTenant();
    return null;
  });
  const { user, logout } = useAuth();
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<SessionStatus>("validating-session");
  const active = useRef<{ controller: AbortController; promise: Promise<void> } | null>(null);
  const isLoading = status === "validating-session" || status === "waiting-for-server";
  const errorMessage = status.endsWith("failed") ? status : null;

  const refresh = useCallback((): Promise<void> => {
    if (active.current) return active.current.promise;
    const controller = new AbortController();
    setCurrentUser(null);
    setStatus("validating-session");
    const promise = validateSession({
      request: (signal) => getCurrentUser(signal),
      refreshToken: async () => {
        if (!user) throw new Error("No local session");
        return user.getIdToken(true);
      },
      signal: controller.signal,
      onStatus: setStatus,
    }).then((result) => {
      if (!result || controller.signal.aborted) return;
      setCurrentUser(result.data?.data ?? null);
      setStatus(result.status);
    }).finally(() => {
      if (active.current?.controller === controller) active.current = null;
    });
    active.current = { controller, promise };
    return promise;
  }, [user]);

  useEffect(() => {
    void refresh();
    return () => { active.current?.controller.abort(); active.current = null; };
  }, [refresh]);

  const value = useMemo<CurrentUserContextValue>(
    () => ({
      currentUser,
      role: currentUser?.role ?? null,
      isLoading,
      errorMessage,
      refresh,
    }),
    [currentUser, errorMessage, isLoading, refresh],
  );

  if (status !== "authenticated" || !currentUser) {
    return <SessionStatusScreen status={status} onRetry={() => void refresh()} onLogin={() => void logout()} />;
  }

  return (
    <CurrentUserContext.Provider value={value}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser() {
  const context = useContext(CurrentUserContext);

  if (!context) {
    throw new Error("useCurrentUser must be used within CurrentUserProvider");
  }

  return context;
}
