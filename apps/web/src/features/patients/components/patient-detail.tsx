"use client";

import { FileText, Stethoscope } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { createConsultation } from "@/services/consultations";
import { createExam } from "@/services/exams";
import { getOwner } from "@/services/owners";
import { getPatientClinicalHistory } from "@/services/patients";
import type {
  ClinicalHistory,
  ClinicalHistoryTimelineItem,
  Consultation,
  CreateConsultationPayload,
  CreateExamPayload,
  Owner,
} from "@/types/api";

type PatientDetailProps = {
  patientId: string;
};

type PatientDetailState = {
  isLoading: boolean;
  isSubmitting: boolean;
  clinicalHistory: ClinicalHistory | null;
  owner: Owner | null;
  errorMessage: string | null;
  successMessage: string | null;
  showConsultationForm: boolean;
  showExamForm: boolean;
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

type ExamFormState = {
  exam_type: string;
  requested_at: string;
  consultation_id: string;
  observations: string;
};

const initialFormState: ConsultationFormState = {
  visit_date: toDateTimeLocalValue(new Date()),
  reason: "",
  anamnesis: "",
  clinical_exam: "",
  presumptive_diagnosis: "",
  diagnostic_plan: "",
  therapeutic_plan: "",
  final_diagnosis: "",
  indications: "",
};

const initialExamFormState: ExamFormState = {
  exam_type: "",
  requested_at: toDateTimeLocalValue(new Date()),
  consultation_id: "",
  observations: "",
};

const initialState: PatientDetailState = {
  isLoading: true,
  isSubmitting: false,
  clinicalHistory: null,
  owner: null,
  errorMessage: null,
  successMessage: null,
  showConsultationForm: false,
  showExamForm: false,
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

export function PatientDetail({ patientId }: PatientDetailProps) {
  const [state, setState] = useState<PatientDetailState>(initialState);
  const [formState, setFormState] =
    useState<ConsultationFormState>(initialFormState);
  const [examFormState, setExamFormState] =
    useState<ExamFormState>(initialExamFormState);

  const loadClinicalHistory = useCallback(async () => {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const response = await getPatientClinicalHistory(patientId);
      let owner: Owner | null = null;

      if (response.data.owner) {
        owner = response.data.owner;
      } else if (response.data.patient.owner_id) {
        try {
          const ownerResponse = await getOwner(response.data.patient.owner_id);
          owner = ownerResponse.data;
        } catch {
          owner = null;
        }
      }

      setState((current) => ({
        ...current,
        isLoading: false,
        clinicalHistory: response.data,
        owner,
        errorMessage: null,
      }));
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudo cargar la historia clínica";

      setState((current) => ({
        ...current,
        isLoading: false,
        clinicalHistory: null,
        owner: null,
        errorMessage: message,
      }));
    }
  }, [patientId]);

  useEffect(() => {
    void loadClinicalHistory();
  }, [loadClinicalHistory]);

  async function handleCreateConsultation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreateConsultationPayload = {
      patient_id: patientId,
      visit_date: new Date(formState.visit_date).toISOString(),
      reason: formState.reason.trim(),
      ...buildClinicalPayload(formState),
    };

    setState((current) => ({
      ...current,
      isSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await createConsultation(payload);
      setFormState({
        ...initialFormState,
        visit_date: toDateTimeLocalValue(new Date()),
      });
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Consulta creada correctamente.",
        showConsultationForm: false,
        showExamForm: false,
      }));
      await loadClinicalHistory();
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudo crear la consulta";

      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: message,
      }));
    }
  }

  async function handleCreateExam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreateExamPayload = {
      patient_id: patientId,
      exam_type: examFormState.exam_type.trim(),
      requested_at: new Date(examFormState.requested_at).toISOString(),
      consultation_id: examFormState.consultation_id || null,
      observations: examFormState.observations.trim() || null,
    };

    setState((current) => ({
      ...current,
      isSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await createExam(payload);
      setExamFormState({
        ...initialExamFormState,
        requested_at: toDateTimeLocalValue(new Date()),
      });
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Solicitud de examen creada correctamente.",
        showConsultationForm: false,
        showExamForm: false,
      }));
      await loadClinicalHistory();
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudo crear la solicitud de examen";

      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: message,
      }));
    }
  }

  if (state.isLoading && !state.clinicalHistory) {
    return <div className="panel">Cargando historia clínica...</div>;
  }

  if (state.errorMessage && !state.clinicalHistory) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!state.clinicalHistory) {
    return <div className="empty-state">Paciente no encontrado.</div>;
  }

  const { patient, consultations } = state.clinicalHistory;
  const timeline = getClinicalTimeline(state.clinicalHistory);

  return (
    <div className="page-stack patient-detail-page">
      <section className="detail-hero">
        <Link className="back-link" href="/patients">
          Volver a pacientes
        </Link>
        <div className="detail-hero__main">
          <span className="pet-avatar pet-avatar--large" aria-hidden="true">{getSpeciesInitial(patient.species)}</span>
          <div>
            <h1>{patient.name}</h1>
            <p>
              {patient.species}
              {patient.breed ? ` · ${patient.breed}` : ""}
            </p>
          </div>
        </div>
        <div className="button-row">
          <button
            className="primary-button"
            type="button"
            onClick={() =>
              setState((current) => ({
                ...current,
                showConsultationForm: !current.showConsultationForm,
                showExamForm: false,
                successMessage: null,
              }))
            }
          >
            {state.showConsultationForm ? "Cerrar consulta" : "Nueva consulta"}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() =>
              setState((current) => ({
                ...current,
                showExamForm: !current.showExamForm,
                showConsultationForm: false,
                successMessage: null,
              }))
            }
          >
            {state.showExamForm ? "Cerrar examen" : "Nuevo examen"}
          </button>
        </div>
      </section>

      <section className="summary-grid">
        <article className="panel patient-summary-card">
          <div className="patient-summary-card__header">
            <span className="pet-avatar" aria-hidden="true">{getSpeciesInitial(patient.species)}</span>
            <div>
              <h2>{patient.name}</h2>
              <p>
                {patient.species}
                {patient.breed ? ` · ${patient.breed}` : ""}
              </p>
            </div>
          </div>
          <dl className="metric-list">
            <div><dt>Sexo</dt><dd>{patient.sex ?? "No indicado"}</dd></div>
            <div><dt>Edad</dt><dd>{patient.estimated_age ?? "No indicado"}</dd></div>
            <div><dt>Peso</dt><dd>{patient.weight_kg ? `${patient.weight_kg} kg` : "No indicado"}</dd></div>
          </dl>
          {patient.allergies ? (
            <div className="alert-box">Alergias: {patient.allergies}</div>
          ) : null}
        </article>

        <article className="panel owner-card">
          <div className="section-heading">
            <p className="eyebrow">Responsable</p>
            <h2>Propietario</h2>
          </div>
          {state.owner ? (
            <dl className="owner-details">
              <div><dt>Nombre</dt><dd>{state.owner.full_name}</dd></div>
              <div><dt>Teléfono</dt><dd>{state.owner.phone}</dd></div>
              <div><dt>Correo</dt><dd>{state.owner.email ?? "No indicado"}</dd></div>
              <div><dt>Dirección</dt><dd>{state.owner.address ?? "No indicada"}</dd></div>
            </dl>
          ) : (
            <div className="empty-state">No hay datos del propietario disponibles.</div>
          )}
        </article>
      </section>

      {state.showConsultationForm ? (
        <section className="panel clinical-form-card">
          <div className="section-heading">
            <p className="eyebrow">Consulta</p>
            <h2>Nueva consulta</h2>
            <p>Nota clínica estructurada para este paciente.</p>
          </div>

          <form className="entity-form" onSubmit={handleCreateConsultation}>
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
                    setFormState((current) => ({ ...current, reason: event.target.value }))
                  }
                />
              </label>
            </div>

            <div className="clinical-section-grid">
              {consultationSections.map((section) => (
                <label className="field clinical-section" key={section.key}>
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
            </div>

            <button className="primary-button" disabled={state.isSubmitting} type="submit">
              {state.isSubmitting ? "Guardando..." : "Crear consulta"}
            </button>
          </form>
        </section>
      ) : null}

      {state.showExamForm ? (
        <section className="panel clinical-form-card">
          <div className="section-heading">
            <p className="eyebrow">Exámenes</p>
            <h2>Nuevo examen</h2>
            <p>Solicitud de examen en texto para este paciente.</p>
          </div>

          <form className="entity-form" onSubmit={handleCreateExam}>
            <div className="form-grid">
              <label className="field">
                <span>Tipo de examen</span>
                <input
                  required
                  value={examFormState.exam_type}
                  onChange={(event) =>
                    setExamFormState((current) => ({ ...current, exam_type: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>Solicitado el</span>
                <input
                  required
                  type="datetime-local"
                  value={examFormState.requested_at}
                  onChange={(event) =>
                    setExamFormState((current) => ({
                      ...current,
                      requested_at: event.target.value,
                    }))
                  }
                />
              </label>
            </div>

            <label className="field">
              <span>Consulta</span>
              <select
                value={examFormState.consultation_id}
                onChange={(event) =>
                  setExamFormState((current) => ({
                    ...current,
                    consultation_id: event.target.value,
                  }))
                }
              >
                <option value="">Sin consulta vinculada</option>
                {consultations.map((consultation) => (
                  <option key={consultation.id} value={consultation.id}>
                    {formatDateTime(consultation.visit_date)} - {consultation.reason}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Observaciones</span>
              <textarea
                rows={3}
                value={examFormState.observations}
                onChange={(event) =>
                  setExamFormState((current) => ({ ...current, observations: event.target.value }))
                }
              />
            </label>

            <button className="primary-button" disabled={state.isSubmitting} type="submit">
              {state.isSubmitting ? "Guardando..." : "Crear solicitud de examen"}
            </button>
          </form>
        </section>
      ) : null}

      {state.successMessage ? <p className="success-state">{state.successMessage}</p> : null}
      {state.errorMessage && !state.isLoading ? <p className="error-state">{state.errorMessage}</p> : null}

      <section className="panel tabbed-card">
        <div className="tab-list" role="tablist" aria-label="Detalle del paciente">
          <a className="tab-pill tab-pill--active" href="#historia">Historia</a>
          <a className="tab-pill" href="#informacion">Información</a>
          <a className="tab-pill" href="#vacunas">Vacunas</a>
          <a className="tab-pill" href="#archivos">Archivos</a>
        </div>

        <section id="historia" className="tab-section">
          <div className="section-heading">
            <p className="eyebrow">Timeline</p>
            <h2>Historia clínica</h2>
            <p>Consultas y exámenes ordenados por fecha clínica.</p>
          </div>

          {state.isLoading ? <div className="panel-note">Actualizando historia clínica...</div> : null}

          {!state.isLoading && timeline.length === 0 ? (
            <div className="empty-state">No hay consultas ni exámenes registrados para este paciente.</div>
          ) : null}

          {timeline.length > 0 ? (
            <ol className="clinical-timeline">
              {timeline.map((item) => (
                <li className={`clinical-timeline__item clinical-timeline__item--${item.type}`} key={`${item.type}-${item.id}`}>
                  <span className="clinical-timeline__dot" aria-hidden="true">
                    {item.type === "exam" ? <FileText size={18} /> : <Stethoscope size={18} />}
                  </span>
                  <Link className="clinical-timeline__card" href={item.type === "exam" ? `/exams/${item.id}` : `/consultations/${item.id}`}>
                    <span className={`badge badge--${item.type === "exam" ? "blue" : "success"}`}>
                      {item.type === "exam" ? "Examen" : "Consulta"}
                    </span>
                    <time dateTime={item.date}>{formatDateTime(item.date)}</time>
                    <h3>{item.title}</h3>
                    <p>{item.summary}</p>
                    <span className="inline-link">Ver</span>
                  </Link>
                </li>
              ))}
            </ol>
          ) : null}
        </section>

        <section id="informacion" className="tab-section tab-section--soft">
          <h2>Información</h2>
          <dl className="detail-grid">
            <div><dt>Especie</dt><dd>{patient.species}</dd></div>
            <div><dt>Raza</dt><dd>{patient.breed ?? "No indicado"}</dd></div>
            <div><dt>Sexo</dt><dd>{patient.sex ?? "No indicado"}</dd></div>
            <div><dt>Edad estimada</dt><dd>{patient.estimated_age ?? "No indicado"}</dd></div>
            <div><dt>Peso</dt><dd>{patient.weight_kg ? `${patient.weight_kg} kg` : "No indicado"}</dd></div>
            <div><dt>Condiciones crónicas</dt><dd>{patient.chronic_conditions ?? "Sin registros"}</dd></div>
          </dl>
        </section>

        <section id="vacunas" className="tab-section tab-section--soft">
          <h2>Vacunas</h2>
          <div className="empty-state">Módulo en construcción. Esta funcionalidad estará disponible en una próxima versión.</div>
        </section>

        <section id="archivos" className="tab-section tab-section--soft">
          <h2>Archivos</h2>
          <div className="empty-state">Módulo en construcción. Esta funcionalidad estará disponible en una próxima versión.</div>
        </section>
      </section>
    </div>
  );
}

function buildClinicalPayload(formState: ConsultationFormState) {
  return Object.fromEntries(
    consultationSections.map((section) => {
      const value = formState[section.key].trim();
      return [section.key, value || null];
    }),
  );
}

function toDateTimeLocalValue(date: Date) {
  const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getConsultationSummary(consultation: Consultation) {
  return (
    consultation.final_diagnosis ??
    consultation.presumptive_diagnosis ??
    consultation.clinical_exam ??
    consultation.anamnesis ??
    "Sin resumen clínico registrado."
  );
}

function getClinicalTimeline(
  clinicalHistory: ClinicalHistory,
): ClinicalHistoryTimelineItem[] {
  if (clinicalHistory.timeline) {
    return clinicalHistory.timeline;
  }

  return clinicalHistory.consultations.map((consultation) => ({
    type: "consultation",
    id: consultation.id,
    date: consultation.visit_date,
    title: consultation.reason,
    summary: getConsultationSummary(consultation),
  }));
}

function getSpeciesInitial(species: string) {
  return species.trim().charAt(0).toUpperCase() || "P";
}
