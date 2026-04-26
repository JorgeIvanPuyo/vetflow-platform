"use client";

import {
  AlertCircle,
  CalendarPlus,
  ClipboardPlus,
  PackagePlus,
  PawPrint,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { getOwners } from "@/services/owners";
import { getPatients } from "@/services/patients";
import { getBackendHealth } from "@/services/system";

type DashboardState = {
  isLoading: boolean;
  backendStatus: string | null;
  ownerCount: number;
  patientCount: number;
  errorMessage: string | null;
};

const initialState: DashboardState = {
  isLoading: true,
  backendStatus: null,
  ownerCount: 0,
  patientCount: 0,
  errorMessage: null,
};

export function DashboardHome() {
  const [state, setState] = useState<DashboardState>(initialState);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboard() {
      try {
        const [health, owners, patients] = await Promise.all([
          getBackendHealth(),
          getOwners(),
          getPatients(),
        ]);

        if (!isMounted) {
          return;
        }

        setState({
          isLoading: false,
          backendStatus: health.status,
          ownerCount: owners.meta.total,
          patientCount: patients.meta.total,
          errorMessage: null,
        });
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message =
          getApiErrorMessage(error);

        setState({
          isLoading: false,
          backendStatus: null,
          ownerCount: 0,
          patientCount: 0,
          errorMessage: message,
        });
      }
    }

    void loadDashboard();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="page-stack dashboard-page">
      <section className="screen-heading">
        <p className="eyebrow">VetClinic</p>
        <h1>Dashboard</h1>
        <p>Resumen de tu clínica veterinaria</p>
      </section>

      {state.errorMessage ? (
        <section className="error-state">
          <strong>Error de conexión:</strong> {state.errorMessage}
        </section>
      ) : null}

      <section className="kpi-grid" aria-label="Indicadores principales">
        <KpiCard
          icon={<CalendarPlus size={22} />}
          label="Turnos hoy"
          value="0"
          tone="blue"
          helper="Módulo agenda pendiente"
        />
        <KpiCard
          icon={<Stethoscope size={22} />}
          label="Consultas semana"
          value={state.isLoading ? "..." : String(state.patientCount)}
          tone="success"
          helper="Referencia temporal por pacientes activos"
        />
        <KpiCard
          icon={<AlertCircle size={22} />}
          label="Alertas stock"
          value="0"
          tone="warning"
          helper="Inventario en construcción"
        />
        <KpiCard
          icon={<PawPrint size={22} />}
          label="Venc. próximos"
          value={state.isLoading ? "..." : String(state.ownerCount)}
          tone="danger"
          helper="Dato temporal del MVP"
        />
      </section>

      <section className="panel quick-actions-card">
        <div className="section-heading section-heading--row">
          <div>
            <p className="eyebrow">Acciones rápidas</p>
            <h2>Atajos clínicos</h2>
          </div>
          <span className={`status-pill ${state.backendStatus ? "status-pill--ok" : "status-pill--loading"}`}>
            API {state.backendStatus ?? "..."}
          </span>
        </div>

        <div className="quick-actions-grid">
          <Link className="quick-action" href="/patients">
            <span className="icon-bubble"><PawPrint size={22} /></span>
            <span>Nuevo paciente</span>
          </Link>
          <Link className="quick-action" href="/patients">
            <span className="icon-bubble icon-bubble--blue"><ClipboardPlus size={22} /></span>
            <span>Nueva consulta</span>
          </Link>
          <Link className="quick-action" href="/inventario">
            <span className="icon-bubble icon-bubble--warning"><PackagePlus size={22} /></span>
            <span>Registrar compra</span>
          </Link>
          <Link className="quick-action" href="/agenda">
            <span className="icon-bubble icon-bubble--danger"><CalendarPlus size={22} /></span>
            <span>Crear turno</span>
          </Link>
        </div>
      </section>
    </div>
  );
}

function KpiCard({
  icon,
  label,
  value,
  helper,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  helper: string;
  tone: "blue" | "success" | "warning" | "danger";
}) {
  return (
    <article className={`kpi-card kpi-card--${tone}`}>
      <span className="kpi-card__icon">{icon}</span>
      <span className="kpi-card__value">{value}</span>
      <h2>{label}</h2>
      <p>{helper}</p>
    </article>
  );
}
