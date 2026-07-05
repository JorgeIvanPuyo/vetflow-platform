"use client";

import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getApiErrorMessage } from "@/lib/api";
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
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await getCurrentUser();
      setCurrentUser(response.data);
    } catch (error) {
      setCurrentUser(null);
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
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
