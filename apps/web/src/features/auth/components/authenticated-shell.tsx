"use client";

import { ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";
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

  return (
    <div className="app-shell">
      <AppHeader />
      <main className="page-container">{children}</main>
    </div>
  );
}
