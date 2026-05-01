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
import { getClinicProfile } from "@/services/clinic";
import type { ClinicProfile } from "@/types/api";

type ClinicContextValue = {
  profile: ClinicProfile | null;
  displayName: string;
  isLoading: boolean;
  errorMessage: string | null;
  refreshProfile: () => Promise<void>;
};

const ClinicContext = createContext<ClinicContextValue | null>(null);

export function ClinicProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<ClinicProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refreshProfile = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await getClinicProfile();
      setProfile(response.data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshProfile();
  }, [refreshProfile]);

  const value = useMemo<ClinicContextValue>(
    () => ({
      profile,
      displayName: profile?.display_name || profile?.name || "VetClinic",
      isLoading,
      errorMessage,
      refreshProfile,
    }),
    [errorMessage, isLoading, profile, refreshProfile],
  );

  return <ClinicContext.Provider value={value}>{children}</ClinicContext.Provider>;
}

export function useClinic() {
  const context = useContext(ClinicContext);

  if (!context) {
    throw new Error("useClinic must be used within ClinicProvider");
  }

  return context;
}
