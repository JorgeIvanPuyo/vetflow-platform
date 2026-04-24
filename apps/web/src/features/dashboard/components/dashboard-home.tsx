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
            : "No se pudieron cargar los datos del servidor";

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
        <p className="page-subtitle">Base frontend del MVP clínico</p>
        <h1>Conectado al backend multicliente</h1>
        <p>
          Esta pantalla confirma que el frontend puede comunicarse con la API
          FastAPI y leer datos de propietarios del tenant activo.
        </p>
      </section>

      <section className="stats-grid">
        <article className="stat-card">
          <div className="stat-card__label">Estado del backend</div>
          <div className="stat-card__value">
            {state.isLoading ? (
              <span className="status-pill status-pill--loading">Cargando...</span>
            ) : state.errorMessage ? (
              <span className="status-pill status-pill--error">No disponible</span>
            ) : (
              <span className="status-pill status-pill--ok">
                {state.backendStatus ?? "ok"}
              </span>
            )}
          </div>
        </article>

        <article className="stat-card">
          <div className="stat-card__label">Propietarios encontrados</div>
          <div className="stat-card__value">
            {state.isLoading ? "..." : state.ownerCount}
          </div>
        </article>
      </section>

      {state.errorMessage ? (
        <section className="error-state">
          <strong>Error de conexión:</strong> {state.errorMessage}
        </section>
      ) : null}
    </div>
  );
}
