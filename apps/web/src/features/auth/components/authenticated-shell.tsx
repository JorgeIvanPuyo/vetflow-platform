"use client";

import { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { AuthProvider, useAuth } from "@/features/auth/auth-context";
import { LoginForm } from "@/features/auth/components/login-form";

export function AuthenticatedShell({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AuthenticatedContent>{children}</AuthenticatedContent>
    </AuthProvider>
  );
}

function AuthenticatedContent({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <div className="auth-loading">Cargando sesión...</div>;
  }

  if (!user) {
    return <LoginForm />;
  }

  return <AppShell>{children}</AppShell>;
}
