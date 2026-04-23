"use client";

import { useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { getOwners } from "@/services/owners";
import { getBackendHealth } from "@/services/system";

type DashboardState = {
  isLoading: boolean;
  backendStatus: string | null;
  ownerCount: number;
  errorMessage: string | null;
};

const initialState: DashboardState = {
  isLoading: true,
  backendStatus: null,
  ownerCount: 0,
  errorMessage: null,
};

export function DashboardHome() {
  const [state, setState] = useState<DashboardState>(initialState);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboard() {
      try {
        const [health, owners] = await Promise.all([
          getBackendHealth(),
          getOwners(),
        ]);

        if (!isMounted) {
          return;
        }

        setState({
          isLoading: false,
          backendStatus: health.status,
          ownerCount: owners.meta.total,
          errorMessage: null,
        });
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message =
          error instanceof ApiClientError
            ? error.message
            : "Could not load backend data";

        setState({
          isLoading: false,
          backendStatus: null,
          ownerCount: 0,
          errorMessage: message,
        });
      }
    }

    loadDashboard();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">Clinical MVP frontend base</p>
        <h1>Connected to the multi-tenant backend</h1>
        <p>
          This starter screen confirms the frontend can talk to the FastAPI API
          and read tenant-scoped owner data.
        </p>
      </section>

      <section className="stats-grid">
        <article className="stat-card">
          <div className="stat-card__label">Backend status</div>
          <div className="stat-card__value">
            {state.isLoading ? (
              <span className="status-pill status-pill--loading">Loading...</span>
            ) : state.errorMessage ? (
              <span className="status-pill status-pill--error">Unavailable</span>
            ) : (
              <span className="status-pill status-pill--ok">
                {state.backendStatus ?? "ok"}
              </span>
            )}
          </div>
        </article>

        <article className="stat-card">
          <div className="stat-card__label">Owners found</div>
          <div className="stat-card__value">
            {state.isLoading ? "..." : state.ownerCount}
          </div>
        </article>
      </section>

      {state.errorMessage ? (
        <section className="error-state">
          <strong>Connection error:</strong> {state.errorMessage}
        </section>
      ) : null}
    </div>
  );
}
