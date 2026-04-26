"use client";

import { Stethoscope } from "lucide-react";
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
  const { user, isLoading, isTokenLoading } = useAuth();

  if (isLoading || isTokenLoading) {
    return <SessionLoadingScreen />;
  }

  if (!user) {
    return <LoginForm />;
  }

  return <AppShell>{children}</AppShell>;
}

function SessionLoadingScreen() {
  return (
    <main className="auth-loading-screen" aria-live="polite" aria-busy="true">
      <section className="auth-loading-card">
        <span className="brand__mark brand__mark--large" aria-hidden="true">
          <Stethoscope size={28} />
        </span>
        <div>
          <strong>VetClinic</strong>
          <p>Cargando tu sesión...</p>
        </div>
        <span className="loading-spinner" aria-hidden="true" />
      </section>
    </main>
  );
}
