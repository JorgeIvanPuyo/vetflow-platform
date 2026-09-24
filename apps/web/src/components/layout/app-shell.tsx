"use client";

import { ReactNode, Suspense } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { BottomNav } from "@/components/layout/bottom-nav";
import { PageReadBoundary, PageReadContent } from "@/features/connectivity/page-read-boundary";
import { ClinicProvider } from "@/features/clinic/clinic-context";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando sección" />}>
    <PageReadBoundary>
    <div className="app-shell">
      <ClinicProvider>
        <AppSidebar />

        <div className="app-workspace">
          <AppHeader />
          <main className="page-container"><PageReadContent>{children}</PageReadContent></main>
        </div>

        <BottomNav />
      </ClinicProvider>
    </div>
    </PageReadBoundary>
    </Suspense>
  );
}