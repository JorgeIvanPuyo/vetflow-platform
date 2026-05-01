"use client";

import { ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { BottomNav } from "@/components/layout/bottom-nav";
import { ClinicProvider } from "@/features/clinic/clinic-context";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <ClinicProvider>
        <AppHeader />
        <main className="page-container">{children}</main>
        <BottomNav />
      </ClinicProvider>
    </div>
  );
}
