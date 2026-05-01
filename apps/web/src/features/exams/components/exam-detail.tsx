"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { getTraceableUserName } from "@/lib/user-traceability";
import { getExam, updateExam } from "@/services/exams";
import type { Exam, ExamStatus, UpdateExamPayload } from "@/types/api";

type ExamDetailProps = {
  examId: string;
};

type ExamDetailState = {
  isLoading: boolean;
  isSaving: boolean;
  exam: Exam | null;
  errorMessage: string | null;
  successMessage: string | null;
};

type ExamFormState = {
  status: ExamStatus;
  performed_at: string;
  result_summary: string;
  result_detail: string;
  observations: string;
};

const initialState: ExamDetailState = {
  isLoading: true,
  isSaving: false,
  exam: null,
  errorMessage: null,
  successMessage: null,
};

const examStatusOptions: Array<{ value: ExamStatus; label: string }> = [
  { value: "requested", label: "Solicitado" },
  { value: "performed", label: "Realizado" },
  { value: "result_loaded", label: "Resultado cargado" },
];

export function ExamDetail({ examId }: ExamDetailProps) {
  const [state, setState] = useState<ExamDetailState>(initialState);
  const [formState, setFormState] = useState<ExamFormState>({
    status: "requested",
    performed_at: "",
    result_summary: "",
    result_detail: "",
    observations: "",
  });

  useEffect(() => {
    let isMounted = true;

    async function loadExam() {
      try {
        const response = await getExam(examId);

        if (!isMounted) {
          return;
        }

        setState({
          isLoading: false,
          isSaving: false,
          exam: response.data,
          errorMessage: null,
          successMessage: null,
        });
        setFormState(toFormState(response.data));
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message =
          getApiErrorMessage(error);

        setState({
          isLoading: false,
          isSaving: false,
          exam: null,
          errorMessage: message,
          successMessage: null,
        });
      }
    }

    void loadExam();

    return () => {
      isMounted = false;
    };
  }, [examId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: UpdateExamPayload = {
      status: formState.status,
      performed_at: formState.performed_at
        ? new Date(formState.performed_at).toISOString()
        : null,
      result_summary: formState.result_summary.trim() || null,
      result_detail: formState.result_detail.trim() || null,
      observations: formState.observations.trim() || null,
    };

    setState((current) => ({
      ...current,
      isSaving: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateExam(examId, payload);
      setState((current) => ({
        ...current,
        isSaving: false,
        exam: response.data,
        successMessage: "Examen actualizado correctamente.",
      }));
      setFormState(toFormState(response.data));
    } catch (error) {
      const message =
        getApiErrorMessage(error);

      setState((current) => ({
        ...current,
        isSaving: false,
        errorMessage: message,
      }));
    }
  }

  if (state.isLoading) {
    return <div className="loading-card" aria-label="Cargando datos del examen" />;
  }

  if (state.errorMessage && !state.exam) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!state.exam) {
    return <div className="empty-state">Examen no encontrado.</div>;
  }

  const requestedByName = getTraceableUserName(state.exam, "requested_by");

  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">
          <Link href={`/patients/${state.exam.patient_id}`}>Volver al paciente</Link>
        </p>
        <div className="hero-actions">
          <div>
            <h1 className="page-title">{state.exam.exam_type}</h1>
            <p className="page-subtitle">
              Solicitado {formatDateTime(state.exam.requested_at)}
            </p>
          </div>
          <span className={`status-pill status-pill--${state.exam.status}`}>
            {getExamStatusLabel(state.exam.status)}
          </span>
        </div>
      </section>

      <section className="panel">
        <h2>Detalle del examen</h2>
        <dl className="detail-grid">
          <div>
            <dt>Paciente</dt>
            <dd>
              <Link href={`/patients/${state.exam.patient_id}`}>Ver paciente</Link>
            </dd>
          </div>
          <div>
            <dt>Consulta</dt>
            <dd>
              {state.exam.consultation_id ? (
                <Link href={`/consultations/${state.exam.consultation_id}`}>
                  Ver consulta
                </Link>
              ) : (
                "Sin vincular"
              )}
            </dd>
          </div>
          <div>
            <dt>Solicitado el</dt>
            <dd>{formatDateTime(state.exam.requested_at)}</dd>
          </div>
          <div>
            <dt>Realizado el</dt>
            <dd>
              {state.exam.performed_at
                ? formatDateTime(state.exam.performed_at)
                : "No indicado"}
            </dd>
          </div>
          {requestedByName ? (
            <div>
              <dt>Solicitado por</dt>
              <dd>{requestedByName}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Campos de resultado</h2>
          <p className="muted-text">Actualización de estado y resultado en texto.</p>
        </div>

        <form className="entity-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="field">
              <span>Estado</span>
              <select
                value={formState.status}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    status: event.target.value as ExamStatus,
                  }))
                }
              >
                {examStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Realizado el</span>
              <input
                type="datetime-local"
                value={formState.performed_at}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    performed_at: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          <label className="field">
            <span>Resumen del resultado</span>
            <textarea
              rows={3}
              value={formState.result_summary}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  result_summary: event.target.value,
                }))
              }
            />
          </label>

          <label className="field">
            <span>Detalle del resultado</span>
            <textarea
              rows={5}
              value={formState.result_detail}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  result_detail: event.target.value,
                }))
              }
            />
          </label>

          <label className="field">
            <span>Observaciones</span>
            <textarea
              rows={3}
              value={formState.observations}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  observations: event.target.value,
                }))
              }
            />
          </label>

          <button className="primary-button" disabled={state.isSaving} type="submit">
            {state.isSaving ? "Guardando..." : "Guardar examen"}
          </button>
        </form>

        {state.successMessage ? (
          <p className="success-state">{state.successMessage}</p>
        ) : null}
        {state.errorMessage ? (
          <p className="error-state">{state.errorMessage}</p>
        ) : null}
      </section>
    </div>
  );
}

function toFormState(exam: Exam): ExamFormState {
  return {
    status: exam.status,
    performed_at: exam.performed_at ? toDateTimeLocalValue(exam.performed_at) : "",
    result_summary: exam.result_summary ?? "",
    result_detail: exam.result_detail ?? "",
    observations: exam.observations ?? "",
  };
}

function toDateTimeLocalValue(value: string) {
  const date = new Date(value);
  const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getExamStatusLabel(status: ExamStatus) {
  return examStatusOptions.find((option) => option.value === status)?.label ?? status;
}
