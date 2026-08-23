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
import { getClinicConfiguration, getClinicProfile } from "@/services/clinic";
import type { ClinicProfile, TenantPreferences } from "@/types/api";

type ClinicContextValue = {
  profile: ClinicProfile | null;
  preferences: TenantPreferences | null;
  displayName: string;
  isLoading: boolean;
  errorMessage: string | null;
  refreshProfile: () => Promise<void>;
  refreshPreferences: () => Promise<void>;
};

const ClinicContext = createContext<ClinicContextValue | null>(null);

export function ClinicProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<ClinicProfile | null>(null);
  const [preferences, setPreferences] = useState<TenantPreferences | null>(null);
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

  const refreshPreferences = useCallback(async () => {
    try {
      const response = await getClinicConfiguration("preferences");
      setPreferences(response.data.preferences ?? null);
    } catch {
      setPreferences(null);
    }
  }, []);

  useEffect(() => {
    void refreshProfile();
    void refreshPreferences();
  }, [refreshProfile, refreshPreferences]);

  const value = useMemo<ClinicContextValue>(
    () => ({
      profile,
      preferences,
      displayName: profile?.display_name || profile?.name || "VetClinic",
      isLoading,
      errorMessage,
      refreshProfile,
      refreshPreferences,
    }),
    [errorMessage, isLoading, preferences, profile, refreshPreferences, refreshProfile],
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
