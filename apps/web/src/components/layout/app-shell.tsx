"use client";

import { ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { BottomNav } from "@/components/layout/bottom-nav";
import { ClinicProvider } from "@/features/clinic/clinic-context";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <ClinicProvider>
        <AppSidebar />

        <div className="app-workspace">
          <AppHeader />
          <main className="page-container">{children}</main>
        </div>

        <BottomNav />
      </ClinicProvider>
    </div>
  );
}