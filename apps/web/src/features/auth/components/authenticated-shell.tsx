"use client";

import { ReactNode } from "react";

import { SessionStatusScreen } from "./session-status-screen";

import { AppShell } from "@/components/layout/app-shell";
import { AuthProvider, useAuth } from "@/features/auth/auth-context";
import { CurrentUserProvider } from "@/features/auth/current-user-context";
import { LoginForm } from "@/features/auth/components/login-form";

export function AuthenticatedShell({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AuthenticatedContent>{children}</AuthenticatedContent>
    </AuthProvider>
  );
}

function AuthenticatedContent({ children }: { children: ReactNode }) {
  const { user, isLoading, isTokenLoading } = useAuth();

  if (isLoading || isTokenLoading) {
    return <SessionStatusScreen />;
  }

  if (!user) {
    return <LoginForm />;
  }

  return (
    <CurrentUserProvider key={user.uid}>
      <AppShell>{children}</AppShell>
    </CurrentUserProvider>
  );
}
