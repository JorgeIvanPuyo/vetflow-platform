"use client";

import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Search,
  Stethoscope,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { listConsultations } from "@/services/consultations";
import type {
  ConsultationListItem,
  ConsultationStatus,
} from "@/types/api";

type ConsultationStatusFilter = "all" | ConsultationStatus;

type ConsultationsState = {
  isLoading: boolean;
  consultations: ConsultationListItem[];
  errorMessage: string | null;
  meta: {
    page: number;
    page_size: number;
    total: number;
  };
};

const initialState: ConsultationsState = {
  isLoading: true,
  consultations: [],
  errorMessage: null,
  meta: { page: 1, page_size: 12, total: 0 },
};

export function ConsultationsScreen() {
  const [state, setState] = useState<ConsultationsState>(initialState);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ConsultationStatusFilter>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const loadConsultations = useCallback(async () => {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const response = await listConsultations({
        page,
        pageSize,
        search: search || undefined,
        status: status === "all" ? undefined : status,
      });
      setState({
        isLoading: false,
        consultations: response.data,
        errorMessage: null,
        meta: response.meta,
      });
    } catch {
      setState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: "No fue posible cargar las consultas.",
      }));
    }
  }, [page, pageSize, search, status]);

  useEffect(() => {
    void loadConsultations();
  }, [loadConsultations]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  const hasFilters = Boolean(search || status !== "all");
  const emptyMessage = hasFilters
    ? "No se encontraron consultas con los filtros aplicados."
    : "No hay consultas registradas.";

  return (
    <div className="page-stack consultations-list-page">
      <section className="screen-heading list-page__header">
        <div>
          <h1>Consultas</h1>
          <p>
            {state.isLoading && state.meta.total === 0
              ? "Cargando consultas..."
              : `${state.meta.total} consulta${state.meta.total === 1 ? "" : "s"} registrada${state.meta.total === 1 ? "" : "s"}`}
          </p>
        </div>
      </section>

      <section className="panel consultations-list-toolbar">
        <form className="search-form" onSubmit={handleSearch}>
          <label className="search-field">
            <Search aria-hidden="true" size={18} />
            <span className="sr-only">Buscar consultas</span>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Buscar por paciente, propietario o motivo"
            />
          </label>
          <button className="search-button" type="submit">Buscar</button>
        </form>
        <label className="consultations-status-filter">
          <span>Estado</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as ConsultationStatusFilter);
              setPage(1);
            }}
          >
            <option value="all">Todos</option>
            <option value="draft">Borrador</option>
            <option value="completed">Completada</option>
          </select>
        </label>
      </section>

      {state.isLoading && state.consultations.length === 0 ? (
        <div className="loading-card" aria-label="Cargando consultas" />
      ) : null}

      {!state.isLoading && state.errorMessage ? (
        <section className="error-state">
          {state.errorMessage}
          <button
            className="secondary-button secondary-button--full"
            type="button"
            onClick={() => void loadConsultations()}
          >
            Reintentar
          </button>
        </section>
      ) : null}

      {!state.isLoading && !state.errorMessage && state.consultations.length === 0 ? (
        <div className="empty-state">{emptyMessage}</div>
      ) : null}

      {!state.errorMessage && state.consultations.length > 0 ? (
        <section
          className="consultation-list-grid"
          aria-label="Lista de consultas"
          aria-busy={state.isLoading}
        >
          {state.consultations.map((consultation) => (
            <ConsultationCard key={consultation.id} consultation={consultation} />
          ))}
        </section>
      ) : null}

      {!state.errorMessage && state.meta.total > 0 ? (
        <section className="panel list-pagination" aria-label="Paginación de consultas">
          <label className="list-page-size-control">
            <span>Mostrar</span>
            <select
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(1);
              }}
            >
              <option value={12}>12</option>
              <option value={24}>24</option>
              <option value={48}>48</option>
            </select>
          </label>
          <span className="list-pagination__range">
            {(state.meta.page - 1) * state.meta.page_size + 1}–
            {Math.min(state.meta.page * state.meta.page_size, state.meta.total)} de {state.meta.total}
          </span>
          <div className="list-pagination__actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={state.meta.page <= 1 || state.isLoading}
              aria-label="Página anterior de consultas"
            >
              <ChevronLeft aria-hidden="true" size={18} />
              Anterior
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => setPage((current) => current + 1)}
              disabled={
                state.meta.page * state.meta.page_size >= state.meta.total
                || state.isLoading
              }
              aria-label="Página siguiente de consultas"
            >
              Siguiente
              <ChevronRight aria-hidden="true" size={18} />
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ConsultationCard({ consultation }: { consultation: ConsultationListItem }) {
  const diagnosis = consultation.final_diagnosis || consultation.presumptive_diagnosis;
  const veterinarian =
    consultation.attending_user_name || consultation.created_by_user_name;

  return (
    <Link className="consultation-list-card" href={`/consultations/${consultation.id}`}>
      <span className="consultation-list-card__icon" aria-hidden="true">
        <Stethoscope size={20} />
      </span>
      <span className="consultation-list-card__body">
        <span className="consultation-list-card__heading">
          <strong>{consultation.patient_name}</strong>
          <span className={getStatusClass(consultation.status)}>
            {getStatusLabel(consultation.status)}
          </span>
        </span>
        <span className="consultation-list-card__date">
          <CalendarDays aria-hidden="true" size={14} />
          {formatConsultationDate(consultation.visit_date)}
        </span>
        <span className="consultation-list-card__reason">
          <small>Motivo</small>
          {consultation.reason}
        </span>
        <span className="consultation-list-card__meta">
          <span><UserRound aria-hidden="true" size={14} /> {consultation.owner_name}</span>
          {veterinarian ? (
            <span><Stethoscope aria-hidden="true" size={14} /> {veterinarian}</span>
          ) : null}
        </span>
        {diagnosis ? (
          <span className="consultation-list-card__diagnosis">
            <small>Diagnóstico</small>
            {diagnosis}
          </span>
        ) : null}
      </span>
      <span className="list-page__chevron" aria-hidden="true">
        <ChevronRight size={16} />
      </span>
    </Link>
  );
}

function formatConsultationDate(value: string) {
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getStatusLabel(status: ConsultationStatus) {
  return status === "completed" ? "Completada" : "Borrador";
}

function getStatusClass(status: ConsultationStatus) {
  return status === "completed" ? "badge badge--success" : "badge badge--warning";
}
