"use client";

import {
  Cat,
  Dog,
  FileText,
  FolderOpen,
  History,
  Info,
  Mail,
  MapPin,
  PawPrint,
  Phone,
  Plus,
  Stethoscope,
  Syringe,
  User,
  X,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { createConsultation } from "@/services/consultations";
import { createExam } from "@/services/exams";
import { createPatientFileReference, getPatientFileReferences } from "@/services/file-references";
import { getOwner } from "@/services/owners";
import { getPatientClinicalHistory } from "@/services/patients";
import { createPreventiveCare, getPatientPreventiveCare } from "@/services/preventive-care";
import type {
  ClinicalHistory,
  ClinicalHistoryTimelineItem,
  Consultation,
  CreateConsultationPayload,
  CreateExamPayload,
  CreatePatientFileReferencePayload,
  CreatePreventiveCarePayload,
  Owner,
  Patient,
  PatientFileReference,
  PreventiveCare,
  PreventiveCareType,
} from "@/types/api";

type PatientDetailProps = {
  patientId: string;
};

type PatientDetailState = {
  isLoading: boolean;
  isSubmitting: boolean;
  isPreventiveSubmitting: boolean;
  isFileSubmitting: boolean;
  clinicalHistory: ClinicalHistory | null;
  owner: Owner | null;
  preventiveCare: PreventiveCare[];
  fileReferences: PatientFileReference[];
  errorMessage: string | null;
  successMessage: string | null;
  showConsultationForm: boolean;
  showExamForm: boolean;
};

type PatientDetailSection = "history" | "info" | "preventive" | "files";
type TimelineFilter = "all" | "consultation" | "exam" | "preventive_care" | "file_reference";

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

type PreventiveCareFormState = {
  name: string;
  care_type: PreventiveCareType;
  applied_at: string;
  next_due_at: string;
  lot_number: string;
  notes: string;
};

type FileReferenceFormState = {
  name: string;
  file_type: string;
  description: string;
  external_url: string;
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

const initialPreventiveCareFormState: PreventiveCareFormState = {
  name: "",
  care_type: "vaccine",
  applied_at: toDateTimeLocalValue(new Date()),
  next_due_at: "",
  lot_number: "",
  notes: "",
};

const initialFileReferenceFormState: FileReferenceFormState = {
  name: "",
  file_type: "radiography",
  description: "",
  external_url: "",
};

const initialState: PatientDetailState = {
  isLoading: true,
  isSubmitting: false,
  isPreventiveSubmitting: false,
  isFileSubmitting: false,
  clinicalHistory: null,
  owner: null,
  preventiveCare: [],
  fileReferences: [],
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

const patientSections: Array<{
  key: PatientDetailSection;
  label: string;
  icon: ReactNode;
}> = [
  { key: "history", label: "Historial completo", icon: <History size={18} /> },
  { key: "info", label: "Información", icon: <Info size={18} /> },
  { key: "preventive", label: "Vacunas y desparasitación", icon: <Syringe size={18} /> },
  { key: "files", label: "Archivos adjuntos", icon: <FolderOpen size={18} /> },
];

const timelineFilters: Array<{ value: TimelineFilter; label: string }> = [
  { value: "all", label: "Todo" },
  { value: "consultation", label: "Consultas" },
  { value: "exam", label: "Exámenes" },
  { value: "preventive_care", label: "Vacunas/desparasitación" },
  { value: "file_reference", label: "Archivos" },
];

const preventiveCareTypeOptions: Array<{ value: PreventiveCareType; label: string }> = [
  { value: "vaccine", label: "Vacuna" },
  { value: "deworming", label: "Desparasitación" },
  { value: "other", label: "Otro" },
];

const fileTypeOptions = [
  { value: "radiography", label: "Radiografía" },
  { value: "laboratory", label: "Laboratorio" },
  { value: "ultrasound", label: "Ecografía" },
  { value: "clinical_photo", label: "Foto clínica" },
  { value: "other", label: "Otro" },
];

export function PatientDetail({ patientId }: PatientDetailProps) {
  const [state, setState] = useState<PatientDetailState>(initialState);
  const [activeSection, setActiveSection] = useState<PatientDetailSection>("history");
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>("all");
  const [isPreventiveModalOpen, setIsPreventiveModalOpen] = useState(false);
  const [isFileModalOpen, setIsFileModalOpen] = useState(false);
  const [formState, setFormState] = useState<ConsultationFormState>(initialFormState);
  const [examFormState, setExamFormState] = useState<ExamFormState>(initialExamFormState);
  const [preventiveFormState, setPreventiveFormState] = useState<PreventiveCareFormState>(initialPreventiveCareFormState);
  const [fileFormState, setFileFormState] = useState<FileReferenceFormState>(initialFileReferenceFormState);

  const loadPatientDetail = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, errorMessage: null }));

    try {
      const [historyResponse, preventiveResponse, fileReferenceResponse] = await Promise.all([
        getPatientClinicalHistory(patientId),
        getPatientPreventiveCare(patientId),
        getPatientFileReferences(patientId),
      ]);
      let owner: Owner | null = null;

      if (historyResponse.data.owner) {
        owner = historyResponse.data.owner;
      } else if (historyResponse.data.patient.owner_id) {
        try {
          const ownerResponse = await getOwner(historyResponse.data.patient.owner_id);
          owner = ownerResponse.data;
        } catch {
          owner = null;
        }
      }

      setState((current) => ({
        ...current,
        isLoading: false,
        clinicalHistory: historyResponse.data,
        preventiveCare: preventiveResponse.data,
        fileReferences: fileReferenceResponse.data,
        owner,
        errorMessage: null,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        clinicalHistory: null,
        owner: null,
        preventiveCare: [],
        fileReferences: [],
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [patientId]);

  useEffect(() => {
    void loadPatientDetail();
  }, [loadPatientDetail]);

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
      setFormState({ ...initialFormState, visit_date: toDateTimeLocalValue(new Date()) });
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Consulta creada correctamente.",
        showConsultationForm: false,
        showExamForm: false,
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: getApiErrorMessage(error),
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
      setExamFormState({ ...initialExamFormState, requested_at: toDateTimeLocalValue(new Date()) });
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Solicitud de examen creada correctamente.",
        showConsultationForm: false,
        showExamForm: false,
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleCreatePreventiveCare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreatePreventiveCarePayload = {
      name: preventiveFormState.name.trim(),
      care_type: preventiveFormState.care_type,
      applied_at: new Date(preventiveFormState.applied_at).toISOString(),
      next_due_at: preventiveFormState.next_due_at
        ? new Date(preventiveFormState.next_due_at).toISOString()
        : null,
      lot_number: preventiveFormState.lot_number.trim() || null,
      notes: preventiveFormState.notes.trim() || null,
    };

    setState((current) => ({
      ...current,
      isPreventiveSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await createPreventiveCare(patientId, payload);
      setPreventiveFormState({
        ...initialPreventiveCareFormState,
        applied_at: toDateTimeLocalValue(new Date()),
      });
      setIsPreventiveModalOpen(false);
      setActiveSection("preventive");
      setState((current) => ({
        ...current,
        isPreventiveSubmitting: false,
        successMessage: "Registro preventivo agregado correctamente.",
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isPreventiveSubmitting: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleCreateFileReference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreatePatientFileReferencePayload = {
      name: fileFormState.name.trim(),
      file_type: fileFormState.file_type,
      description: fileFormState.description.trim() || null,
      external_url: fileFormState.external_url.trim() || null,
    };

    setState((current) => ({
      ...current,
      isFileSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await createPatientFileReference(patientId, payload);
      setFileFormState(initialFileReferenceFormState);
      setIsFileModalOpen(false);
      setActiveSection("files");
      setState((current) => ({
        ...current,
        isFileSubmitting: false,
        successMessage: "Referencia de archivo agregada correctamente.",
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isFileSubmitting: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  const timeline = useMemo(() => {
    if (!state.clinicalHistory) {
      return [];
    }

    const allItems = getClinicalTimeline(state.clinicalHistory);
    return timelineFilter === "all"
      ? allItems
      : allItems.filter((item) => item.type === timelineFilter);
  }, [state.clinicalHistory, timelineFilter]);

  if (state.isLoading && !state.clinicalHistory) {
    return <div className="loading-card" aria-label="Cargando historia clínica" />;
  }

  if (state.errorMessage && !state.clinicalHistory) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!state.clinicalHistory) {
    return <div className="empty-state">Paciente no encontrado.</div>;
  }

  const { patient, consultations } = state.clinicalHistory;

  return (
    <div className="page-stack patient-detail-page">
      <section className="detail-hero patient-detail-hero">
        <Link className="back-link" href="/patients">
          Volver a pacientes
        </Link>
        <div className="detail-hero__main">
          <span className={`pet-avatar pet-avatar--large ${getSexAvatarClass(patient.sex)}`} aria-hidden="true">
            {getSpeciesIcon(patient.species, 30)}
          </span>
          <div>
            <h1>{patient.name}</h1>
            <p>
              {patient.breed ? `${patient.breed} · ` : ""}
              {patient.species}
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
            <Stethoscope aria-hidden="true" size={18} />
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
            <FileText aria-hidden="true" size={18} />
            {state.showExamForm ? "Cerrar examen" : "Nuevo examen"}
          </button>
        </div>
      </section>

      <section className="panel patient-profile-card">
        <div className="patient-profile-card__main">
          <span className={`pet-avatar pet-avatar--large ${getSexAvatarClass(patient.sex)}`} aria-hidden="true">
            {getSpeciesIcon(patient.species, 30)}
          </span>
          <div>
            <p className="eyebrow">Paciente</p>
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

        {hasClinicalText(patient.allergies) ? (
          <div className="alert-box alert-box--structured">
            <strong>Alergias</strong>
            <span>{patient.allergies}</span>
          </div>
        ) : null}

        <section className="owner-inline-card" aria-label="Propietario">
          <div className="section-heading">
            <p className="eyebrow">Responsable</p>
            <h2>Propietario</h2>
          </div>
          {state.owner ? (
            <dl className="owner-details owner-details--compact">
              <div><dt>Nombre</dt><dd><User size={15} /> {state.owner.full_name}</dd></div>
              <div><dt>Teléfono</dt><dd><Phone size={15} /> {state.owner.phone}</dd></div>
              {state.owner.email ? <div><dt>Correo</dt><dd><Mail size={15} /> {state.owner.email}</dd></div> : null}
              {state.owner.address ? <div><dt>Dirección</dt><dd><MapPin size={15} /> {state.owner.address}</dd></div> : null}
            </dl>
          ) : (
            <div className="empty-state">No hay datos del propietario disponibles.</div>
          )}
        </section>
      </section>

      {state.showConsultationForm ? renderConsultationForm() : null}
      {state.showExamForm ? renderExamForm(consultations) : null}

      {state.successMessage ? <p className="success-state">{state.successMessage}</p> : null}
      {state.errorMessage && !state.isLoading ? <p className="error-state">{state.errorMessage}</p> : null}
      {state.isLoading ? <div className="panel-note">Actualizando datos del paciente...</div> : null}

      <nav className="patient-section-nav" aria-label="Secciones del paciente">
        {patientSections.map((section) => (
          <button
            aria-label={section.label}
            aria-pressed={activeSection === section.key}
            className={activeSection === section.key ? "patient-section-nav__item patient-section-nav__item--active" : "patient-section-nav__item"}
            key={section.key}
            type="button"
            onClick={() => setActiveSection(section.key)}
          >
            {section.icon}
            <span>{section.label}</span>
          </button>
        ))}
      </nav>

      {activeSection === "history" ? renderHistorySection(timeline) : null}
      {activeSection === "info" ? renderInfoSection(patient) : null}
      {activeSection === "preventive" ? renderPreventiveCareSection() : null}
      {activeSection === "files" ? renderFilesSection() : null}

      {isPreventiveModalOpen ? renderPreventiveCareModal() : null}
      {isFileModalOpen ? renderFileReferenceModal() : null}
    </div>
  );

  function renderConsultationForm() {
    return (
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
                onChange={(event) => setFormState((current) => ({ ...current, visit_date: event.target.value }))}
              />
            </label>

            <label className="field">
              <span>Motivo</span>
              <input
                required
                value={formState.reason}
                onChange={(event) => setFormState((current) => ({ ...current, reason: event.target.value }))}
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
                  onChange={(event) => setFormState((current) => ({ ...current, [section.key]: event.target.value }))}
                />
              </label>
            ))}
          </div>

          <button className="primary-button" disabled={state.isSubmitting} type="submit">
            {state.isSubmitting ? "Guardando..." : "Crear consulta"}
          </button>
        </form>
      </section>
    );
  }

  function renderExamForm(consultations: Consultation[]) {
    return (
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
                onChange={(event) => setExamFormState((current) => ({ ...current, exam_type: event.target.value }))}
              />
            </label>

            <label className="field">
              <span>Solicitado el</span>
              <input
                required
                type="datetime-local"
                value={examFormState.requested_at}
                onChange={(event) => setExamFormState((current) => ({ ...current, requested_at: event.target.value }))}
              />
            </label>
          </div>

          <label className="field">
            <span>Consulta</span>
            <select
              value={examFormState.consultation_id}
              onChange={(event) => setExamFormState((current) => ({ ...current, consultation_id: event.target.value }))}
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
              onChange={(event) => setExamFormState((current) => ({ ...current, observations: event.target.value }))}
            />
          </label>

          <button className="primary-button" disabled={state.isSubmitting} type="submit">
            {state.isSubmitting ? "Guardando..." : "Crear solicitud de examen"}
          </button>
        </form>
      </section>
    );
  }

  function renderHistorySection(timeline: ClinicalHistoryTimelineItem[]) {
    return (
      <section className="panel patient-detail-section">
        <div className="section-heading section-heading--row">
          <div>
            <p className="eyebrow">Timeline</p>
            <h2>Historial completo</h2>
            <p>Consultas, exámenes, vacunas, desparasitación y archivos.</p>
          </div>
          <label className="compact-filter">
            <span className="sr-only">Filtrar historial</span>
            <select value={timelineFilter} onChange={(event) => setTimelineFilter(event.target.value as TimelineFilter)}>
              {timelineFilters.map((filter) => (
                <option key={filter.value} value={filter.value}>{filter.label}</option>
              ))}
            </select>
          </label>
        </div>

        {timeline.length === 0 ? (
          <div className="empty-state">No hay registros para mostrar en este historial.</div>
        ) : (
          <ol className="clinical-timeline">
            {timeline.map((item) => (
              <li className={`clinical-timeline__item clinical-timeline__item--${item.type}`} key={`${item.type}-${item.id}`}>
                <span className="clinical-timeline__dot" aria-hidden="true">
                  {getTimelineIcon(item.type)}
                </span>
                {getTimelineHref(item) ? (
                  <Link className="clinical-timeline__card" href={getTimelineHref(item) ?? "#"}>
                    {renderTimelineContent(item, true)}
                  </Link>
                ) : (
                  <article className="clinical-timeline__card">
                    {renderTimelineContent(item, false)}
                  </article>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    );
  }

  function renderInfoSection(patient: Patient) {
    return (
      <section className="panel patient-detail-section">
        <div className="section-heading">
          <p className="eyebrow">Ficha</p>
          <h2>Información</h2>
          <p>Datos generales registrados para este paciente.</p>
        </div>
        <dl className="detail-grid">
          <div><dt>Nombre</dt><dd>{patient.name}</dd></div>
          <div><dt>Especie</dt><dd>{patient.species}</dd></div>
          <div><dt>Raza</dt><dd>{patient.breed ?? "No indicado"}</dd></div>
          <div><dt>Sexo</dt><dd>{patient.sex ?? "No indicado"}</dd></div>
          <div><dt>Edad estimada</dt><dd>{patient.estimated_age ?? "No indicado"}</dd></div>
          <div><dt>Peso</dt><dd>{patient.weight_kg ? `${patient.weight_kg} kg` : "No indicado"}</dd></div>
          <div><dt>Alergias</dt><dd>{hasClinicalText(patient.allergies) ? patient.allergies : "Sin registros"}</dd></div>
          <div><dt>Condiciones crónicas</dt><dd>{patient.chronic_conditions ?? "Sin registros"}</dd></div>
          <div><dt>Fecha de creación</dt><dd>{formatDateTime(patient.created_at)}</dd></div>
        </dl>
      </section>
    );
  }

  function renderPreventiveCareSection() {
    return (
      <section className="panel patient-detail-section">
        <div className="section-heading section-heading--row">
          <div>
            <p className="eyebrow">Prevención</p>
            <h2>Vacunas y desparasitación</h2>
            <p>Registros preventivos persistentes del paciente.</p>
          </div>
          <button className="primary-button" type="button" onClick={() => setIsPreventiveModalOpen(true)}>
            <Plus aria-hidden="true" size={18} /> Agregar
          </button>
        </div>

        {state.preventiveCare.length === 0 ? (
          <div className="empty-state">No hay vacunas o desparasitaciones registradas.</div>
        ) : (
          <div className="record-card-list">
            {state.preventiveCare.map((record) => (
              <article className="record-card" key={record.id}>
                <span className="icon-bubble"><Syringe size={20} /></span>
                <div>
                  <h3>{record.name}</h3>
                  <p>{getPreventiveCareTypeLabel(record.care_type)} · Aplicado {formatDateTime(record.applied_at)}</p>
                  {record.next_due_at ? <p>Próxima dosis: {formatDateTime(record.next_due_at)}</p> : null}
                  {record.lot_number ? <p>Lote: {record.lot_number}</p> : null}
                  {record.notes ? <p>{record.notes}</p> : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    );
  }

  function renderFilesSection() {
    return (
      <section className="panel patient-detail-section">
        <div className="section-heading section-heading--row">
          <div>
            <p className="eyebrow">Referencias</p>
            <h2>Archivos adjuntos</h2>
            <p>Metadatos o enlaces externos, sin carga real de archivos.</p>
          </div>
          <button className="primary-button" type="button" onClick={() => setIsFileModalOpen(true)}>
            <Plus aria-hidden="true" size={18} /> Agregar
          </button>
        </div>

        {state.fileReferences.length === 0 ? (
          <div className="empty-state">No hay archivos registrados</div>
        ) : (
          <div className="record-card-list">
            {state.fileReferences.map((fileReference) => (
              <article className="record-card" key={fileReference.id}>
                <span className="icon-bubble icon-bubble--blue"><FileText size={20} /></span>
                <div>
                  <h3>{fileReference.name}</h3>
                  <p>{getFileTypeLabel(fileReference.file_type)}</p>
                  {fileReference.description ? <p>{fileReference.description}</p> : null}
                  {fileReference.external_url ? (
                    <a className="inline-link" href={fileReference.external_url} rel="noreferrer" target="_blank">
                      Abrir referencia externa
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    );
  }

  function renderPreventiveCareModal() {
    return (
      <div className="modal-backdrop" role="presentation">
        <section aria-labelledby="preventive-care-title" aria-modal="true" className="bottom-sheet" role="dialog">
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Prevención</p>
              <h2 id="preventive-care-title">Agregar vacuna o desparasitación</h2>
            </div>
            <button aria-label="Cancelar" className="icon-button" onClick={() => setIsPreventiveModalOpen(false)} type="button">
              <X aria-hidden="true" size={20} />
            </button>
          </div>

          <form className="entity-form" onSubmit={handleCreatePreventiveCare}>
            <div className="form-grid">
              <label className="field">
                <span>Nombre</span>
                <input required value={preventiveFormState.name} onChange={(event) => setPreventiveFormState((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label className="field">
                <span>Tipo</span>
                <select value={preventiveFormState.care_type} onChange={(event) => setPreventiveFormState((current) => ({ ...current, care_type: event.target.value as PreventiveCareType }))}>
                  {preventiveCareTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Fecha</span>
                <input required type="datetime-local" value={preventiveFormState.applied_at} onChange={(event) => setPreventiveFormState((current) => ({ ...current, applied_at: event.target.value }))} />
              </label>
              <label className="field">
                <span>Próxima dosis</span>
                <input type="datetime-local" value={preventiveFormState.next_due_at} onChange={(event) => setPreventiveFormState((current) => ({ ...current, next_due_at: event.target.value }))} />
              </label>
            </div>
            <label className="field">
              <span>Lote</span>
              <input value={preventiveFormState.lot_number} onChange={(event) => setPreventiveFormState((current) => ({ ...current, lot_number: event.target.value }))} />
            </label>
            <label className="field">
              <span>Notas</span>
              <textarea rows={3} value={preventiveFormState.notes} onChange={(event) => setPreventiveFormState((current) => ({ ...current, notes: event.target.value }))} />
            </label>
            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setIsPreventiveModalOpen(false)} type="button">Cancelar</button>
              <button className="primary-button" disabled={state.isPreventiveSubmitting} type="submit">
                {state.isPreventiveSubmitting ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  }

  function renderFileReferenceModal() {
    return (
      <div className="modal-backdrop" role="presentation">
        <section aria-labelledby="file-reference-title" aria-modal="true" className="bottom-sheet" role="dialog">
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Archivos</p>
              <h2 id="file-reference-title">Agregar referencia</h2>
            </div>
            <button aria-label="Cancelar" className="icon-button" onClick={() => setIsFileModalOpen(false)} type="button">
              <X aria-hidden="true" size={20} />
            </button>
          </div>

          <p className="panel-note">Por ahora solo se registra la referencia del archivo. La carga real de archivos se implementará en una próxima versión.</p>

          <form className="entity-form" onSubmit={handleCreateFileReference}>
            <div className="form-grid">
              <label className="field">
                <span>Nombre del archivo</span>
                <input required value={fileFormState.name} onChange={(event) => setFileFormState((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label className="field">
                <span>Tipo</span>
                <select value={fileFormState.file_type} onChange={(event) => setFileFormState((current) => ({ ...current, file_type: event.target.value }))}>
                  {fileTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            </div>
            <label className="field">
              <span>Descripción</span>
              <textarea rows={3} value={fileFormState.description} onChange={(event) => setFileFormState((current) => ({ ...current, description: event.target.value }))} />
            </label>
            <label className="field">
              <span>URL externa opcional</span>
              <input type="url" value={fileFormState.external_url} onChange={(event) => setFileFormState((current) => ({ ...current, external_url: event.target.value }))} />
            </label>
            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setIsFileModalOpen(false)} type="button">Cancelar</button>
              <button className="primary-button" disabled={state.isFileSubmitting} type="submit">
                {state.isFileSubmitting ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  }
}

function renderTimelineContent(item: ClinicalHistoryTimelineItem, isNavigable: boolean) {
  return (
    <>
      <span className={`badge ${getTimelineBadgeClass(item.type)}`}>{getTimelineTypeLabel(item.type)}</span>
      <time dateTime={item.date}>{formatDateTime(item.date)}</time>
      <h3>{item.title}</h3>
      <p>{item.summary}</p>
      {isNavigable ? <span className="inline-link">Ver</span> : null}
    </>
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

function toDateTimeLocalValue(date: Date | string) {
  const value = typeof date === "string" ? new Date(date) : date;
  const offsetDate = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getClinicalTimeline(clinicalHistory: ClinicalHistory): ClinicalHistoryTimelineItem[] {
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

function getConsultationSummary(consultation: Consultation) {
  return (
    consultation.final_diagnosis ??
    consultation.presumptive_diagnosis ??
    consultation.clinical_exam ??
    consultation.anamnesis ??
    "Sin resumen clínico registrado."
  );
}

function getTimelineHref(item: ClinicalHistoryTimelineItem) {
  if (item.type === "consultation") {
    return `/consultations/${item.id}`;
  }
  if (item.type === "exam") {
    return `/exams/${item.id}`;
  }
  return null;
}

function getTimelineIcon(type: ClinicalHistoryTimelineItem["type"]) {
  if (type === "consultation") return <Stethoscope size={18} />;
  if (type === "exam") return <FileText size={18} />;
  if (type === "preventive_care") return <Syringe size={18} />;
  return <FolderOpen size={18} />;
}

function getTimelineTypeLabel(type: ClinicalHistoryTimelineItem["type"]) {
  const labels = {
    consultation: "Consulta",
    exam: "Examen",
    preventive_care: "Vacuna/desparasitación",
    file_reference: "Archivo",
  };
  return labels[type];
}

function getTimelineBadgeClass(type: ClinicalHistoryTimelineItem["type"]) {
  if (type === "exam" || type === "file_reference") return "badge--blue";
  return "badge--success";
}

function getPreventiveCareTypeLabel(type: PreventiveCareType) {
  const labels: Record<PreventiveCareType, string> = {
    vaccine: "Vacuna",
    deworming: "Desparasitación",
    other: "Otro",
  };
  return labels[type];
}

function getFileTypeLabel(type: string) {
  return fileTypeOptions.find((option) => option.value === type)?.label ?? readableLabel(type);
}

function readableLabel(value: string) {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

function getSpeciesIcon(species: string, size = 24) {
  const normalized = species.trim().toLowerCase();
  if (["canino", "perro", "dog", "canine"].some((word) => normalized.includes(word))) {
    return <Dog size={size} />;
  }
  if (["felino", "gato", "cat", "feline"].some((word) => normalized.includes(word))) {
    return <Cat size={size} />;
  }
  return <PawPrint size={size} />;
}

function getSexAvatarClass(sex: string | null) {
  const normalized = sex?.trim().toLowerCase() ?? "";
  if (["macho", "masculino", "male"].includes(normalized)) {
    return "pet-avatar--male";
  }
  if (["hembra", "femenino", "female"].includes(normalized)) {
    return "pet-avatar--female";
  }
  return "pet-avatar--neutral";
}

function hasClinicalText(value: string | null) {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return Boolean(normalized && !["ninguna", "ninguno", "no", "n/a", "na"].includes(normalized));
}
