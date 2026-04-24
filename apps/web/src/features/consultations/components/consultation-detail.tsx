"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { getConsultation, updateConsultation } from "@/services/consultations";
import { getConsultationExams } from "@/services/exams";
import type {
  Consultation,
  Exam,
  ExamStatus,
  UpdateConsultationPayload,
} from "@/types/api";

type ConsultationDetailProps = {
  consultationId: string;
};

type ConsultationDetailState = {
  isLoading: boolean;
  isSaving: boolean;
  consultation: Consultation | null;
  linkedExams: Exam[];
  errorMessage: string | null;
  successMessage: string | null;
};

type ConsultationFormState = {
  visit_date: string;
  reason: string;
  anamnesis: string;
  clinical_exam: string;
  presumptive_diagnosis: string;
  diagnostic_plan: string;
  therapeutic_plan: string;
  final_diagnosis: string;
  indications: string;
};

const initialState: ConsultationDetailState = {
  isLoading: true,
  isSaving: false,
  consultation: null,
  linkedExams: [],
  errorMessage: null,
  successMessage: null,
};

const initialFormState: ConsultationFormState = {
  visit_date: "",
  reason: "",
  anamnesis: "",
  clinical_exam: "",
  presumptive_diagnosis: "",
  diagnostic_plan: "",
  therapeutic_plan: "",
  final_diagnosis: "",
  indications: "",
};

const consultationSections: Array<{
  key: keyof Omit<ConsultationFormState, "visit_date" | "reason">;
  label: string;
}> = [
  { key: "anamnesis", label: "Anamnesis" },
  { key: "clinical_exam", label: "Examen clínico" },
  { key: "presumptive_diagnosis", label: "Diagnóstico presuntivo" },
  { key: "diagnostic_plan", label: "Plan diagnóstico" },
  { key: "therapeutic_plan", label: "Plan terapéutico" },
  { key: "final_diagnosis", label: "Diagnóstico final" },
  { key: "indications", label: "Indicaciones" },
];

export function ConsultationDetail({ consultationId }: ConsultationDetailProps) {
  const [state, setState] = useState<ConsultationDetailState>(initialState);
  const [formState, setFormState] =
    useState<ConsultationFormState>(initialFormState);

  useEffect(() => {
    let isMounted = true;

    async function loadConsultation() {
      try {
        const [response, examsResponse] = await Promise.all([
          getConsultation(consultationId),
          getConsultationExams(consultationId),
        ]);

        if (!isMounted) {
          return;
        }

        setState({
          isLoading: false,
          isSaving: false,
          consultation: response.data,
          linkedExams: examsResponse.data,
          errorMessage: null,
          successMessage: null,
        });
        setFormState(toFormState(response.data));
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message =
          error instanceof ApiClientError
            ? error.message
            : "No se pudo cargar la consulta";

        setState({
          isLoading: false,
          isSaving: false,
          consultation: null,
          linkedExams: [],
          errorMessage: message,
          successMessage: null,
        });
      }
    }

    void loadConsultation();

    return () => {
      isMounted = false;
    };
  }, [consultationId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: UpdateConsultationPayload = {
      visit_date: new Date(formState.visit_date).toISOString(),
      reason: formState.reason.trim(),
      ...buildClinicalPayload(formState),
    };

    setState((current) => ({
      ...current,
      isSaving: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateConsultation(consultationId, payload);
      setState((current) => ({
        ...current,
        isSaving: false,
        consultation: response.data,
        successMessage: "Consulta actualizada correctamente.",
      }));
      setFormState(toFormState(response.data));
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudo actualizar la consulta";

      setState((current) => ({
        ...current,
        isSaving: false,
        errorMessage: message,
      }));
    }
  }

  if (state.isLoading) {
    return <div className="panel">Cargando consulta...</div>;
  }

  if (state.errorMessage && !state.consultation) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!state.consultation) {
    return <div className="empty-state">Consulta no encontrada.</div>;
  }

  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">
          <Link href={`/patients/${state.consultation.patient_id}`}>
            Volver al paciente
          </Link>
        </p>
        <h1 className="page-title">Consulta</h1>
        <p className="page-subtitle">
          {formatDateTime(state.consultation.visit_date)} ·{" "}
          {state.consultation.reason}
        </p>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Nota clínica</h2>
          <p className="muted-text">Revisa y edita los campos de la consulta.</p>
        </div>

        <form className="entity-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="field">
              <span>Fecha de consulta</span>
              <input
                required
                type="datetime-local"
                value={formState.visit_date}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    visit_date: event.target.value,
                  }))
                }
              />
            </label>

            <label className="field">
              <span>Motivo</span>
              <input
                required
                value={formState.reason}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    reason: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          {consultationSections.map((section) => (
            <label className="field" key={section.key}>
              <span>{section.label}</span>
              <textarea
                rows={3}
                value={formState[section.key]}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    [section.key]: event.target.value,
                  }))
                }
              />
            </label>
          ))}

          <button className="primary-button" disabled={state.isSaving} type="submit">
            {state.isSaving ? "Guardando..." : "Guardar consulta"}
          </button>
        </form>

        {state.successMessage ? (
          <p className="success-state">{state.successMessage}</p>
        ) : null}
        {state.errorMessage ? (
          <p className="error-state">{state.errorMessage}</p>
        ) : null}
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Exámenes vinculados</h2>
          <p className="muted-text">Solicitudes de examen asociadas a esta consulta.</p>
        </div>

        {state.linkedExams.length === 0 ? (
          <div className="empty-state">No hay exámenes vinculados a esta consulta.</div>
        ) : (
          <ul className="simple-list">
            {state.linkedExams.map((exam) => (
              <li className="simple-list__item" key={exam.id}>
                <Link className="simple-list__title-link" href={`/exams/${exam.id}`}>
                  {exam.exam_type}
                </Link>
                <p className="simple-list__meta">
                  {formatDateTime(exam.requested_at)}
                </p>
                <p className="simple-list__meta">
                  Estado: {getExamStatusLabel(exam.status)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function toFormState(consultation: Consultation): ConsultationFormState {
  return {
    visit_date: toDateTimeLocalValue(consultation.visit_date),
    reason: consultation.reason,
    anamnesis: consultation.anamnesis ?? "",
    clinical_exam: consultation.clinical_exam ?? "",
    presumptive_diagnosis: consultation.presumptive_diagnosis ?? "",
    diagnostic_plan: consultation.diagnostic_plan ?? "",
    therapeutic_plan: consultation.therapeutic_plan ?? "",
    final_diagnosis: consultation.final_diagnosis ?? "",
    indications: consultation.indications ?? "",
  };
}

function buildClinicalPayload(formState: ConsultationFormState) {
  return Object.fromEntries(
    consultationSections.map((section) => {
      const value = formState[section.key].trim();
      return [section.key, value || null];
    }),
  );
}

function toDateTimeLocalValue(value: string) {
  const date = new Date(value);
  const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getExamStatusLabel(status: ExamStatus) {
  const labels: Record<ExamStatus, string> = {
    requested: "Solicitado",
    performed: "Realizado",
    result_loaded: "Resultado cargado",
  };

  return labels[status];
}
