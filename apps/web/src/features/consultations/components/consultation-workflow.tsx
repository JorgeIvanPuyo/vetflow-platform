"use client";

import {
  ArrowLeft,
  CalendarCheck,
  Check,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  Package,
  Pill,
  Save,
  Stethoscope,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChangeEvent,
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { ApiClientError, getApiErrorMessage } from "@/lib/api";
import {
  AiClinicalRewriteAction,
  AiConsultationSummaryAction,
} from "@/features/consultations/components/ai-clinical-assist";
import { getTraceableUserName } from "@/lib/user-traceability";
import {
  formatInventoryCurrency,
  formatInventoryQuantity,
  getInventoryCategoryLabel,
  getInventoryUnitLabel,
} from "@/features/inventory/components/inventory-helpers";
import {
  createConsultation,
  createConsultationMedication,
  createConsultationStudyRequest,
  deleteConsultation,
  deleteConsultationMedication,
  deleteConsultationStudyRequest,
  getConsultation,
  updateConsultation,
  updateConsultationStep,
} from "@/services/consultations";
import { searchInventoryMedications } from "@/services/inventory";
import { getPatientClinicalHistory } from "@/services/patients";
import type {
  Consultation,
  ConsultationMedication,
  ConsultationStudyRequest,
  ConsultationStudyRequestType,
  AiPatientContext,
  ConsultationSummaryPayload,
  CreateMedicationPayload,
  CreateStudyRequestPayload,
  InventoryItem,
  Patient,
  StepUpdatePayload,
} from "@/types/api";

type ConsultationWorkflowProps =
  | {
      mode: "new";
      patientId: string;
      consultationId?: never;
    }
  | {
      mode: "edit";
      consultationId: string;
      patientId?: never;
    };

type FormState = {
  visit_date: string;
  reason: string;
  anamnesis: string;
  symptoms: string;
  symptom_duration: string;
  relevant_history: string;
  habits_and_diet: string;
  temperature_c: string;
  current_weight_kg: string;
  heart_rate: string;
  respiratory_rate: string;
  mucous_membranes: string;
  hydration: string;
  physical_exam_findings: string;
  presumptive_diagnosis: string;
  diagnostic_tags: string;
  diagnostic_plan_notes: string;
  diagnostic_results: string;
  therapeutic_plan: string;
  therapeutic_plan_notes: string;
  final_diagnosis: string;
  indications: string;
  next_control_date: string;
  reminder_requested: boolean;
  consultation_summary: string;
};

type ClinicalTextField =
  | "symptoms"
  | "relevant_history"
  | "physical_exam_findings"
  | "presumptive_diagnosis"
  | "diagnostic_plan_notes"
  | "diagnostic_results"
  | "therapeutic_plan"
  | "therapeutic_plan_notes"
  | "final_diagnosis"
  | "indications"
  | "consultation_summary";

type StudyFormState = {
  name: string;
  study_type: ConsultationStudyRequestType;
  notes: string;
};

type MedicationFormState = {
  medication_name: string;
  dose_or_quantity: string;
  instructions: string;
};

type MedicationMode = "manual" | "inventory";

type InventoryMedicationFormState = {
  search: string;
  quantity_used: string;
  dose_or_quantity: string;
  instructions: string;
};

type ToastState = {
  title: string;
  detail?: string;
  variant: "success" | "error";
};

const steps = [
  { id: 1, label: "Anamnesis" },
  { id: 2, label: "Examen" },
  { id: 3, label: "Diagnóstico presuntivo" },
  { id: 4, label: "Plan diagnóstico" },
  { id: 5, label: "Resultados diagnósticos" },
  { id: 6, label: "Plan terapéutico" },
  { id: 7, label: "Diagnóstico final" },
  { id: 8, label: "Indicaciones" },
] as const;

const initialFormState: FormState = {
  visit_date: toDateTimeLocalValue(new Date()),
  reason: "",
  anamnesis: "",
  symptoms: "",
  symptom_duration: "",
  relevant_history: "",
  habits_and_diet: "",
  temperature_c: "",
  current_weight_kg: "",
  heart_rate: "",
  respiratory_rate: "",
  mucous_membranes: "",
  hydration: "",
  physical_exam_findings: "",
  presumptive_diagnosis: "",
  diagnostic_tags: "",
  diagnostic_plan_notes: "",
  diagnostic_results: "",
  therapeutic_plan: "",
  therapeutic_plan_notes: "",
  final_diagnosis: "",
  indications: "",
  next_control_date: "",
  reminder_requested: false,
  consultation_summary: "",
};

const initialStudyFormState: StudyFormState = {
  name: "",
  study_type: "laboratory",
  notes: "",
};

const initialMedicationFormState: MedicationFormState = {
  medication_name: "",
  dose_or_quantity: "",
  instructions: "",
};

const initialInventoryMedicationFormState: InventoryMedicationFormState = {
  search: "",
  quantity_used: "",
  dose_or_quantity: "",
  instructions: "",
};

const mucousMembraneOptions = ["Rosadas", "Pálidas", "Congestivas", "Cianóticas", "Ictéricas"];
const hydrationOptions = ["Normal", "Leve deshidratación", "Moderada", "Severa"];

function getStepIcon(stepId: (typeof steps)[number]["id"]) {
  switch (stepId) {
    case 1:
      return <Stethoscope size={12} />;
    case 2:
      return <CalendarCheck size={12} />;
    case 3:
      return <Stethoscope size={12} />;
    case 4:
      return <FlaskConical size={12} />;
    case 5:
      return <FlaskConical size={12} />;
    case 6:
      return <Pill size={12} />;
    case 7:
      return <Check size={12} />;
    case 8:
      return <ChevronRight size={12} />;
  }
}

export function ConsultationWorkflow(props: ConsultationWorkflowProps) {
  const router = useRouter();
  const hasStartedRef = useRef(false);
  const previousStepRef = useRef<number | null>(null);
  const workflowRef = useRef<HTMLDivElement | null>(null);
  const toastTimeoutRef = useRef<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isAddingStudy, setIsAddingStudy] = useState(false);
  const [isAddingMedication, setIsAddingMedication] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [consultation, setConsultation] = useState<Consultation | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [activeStep, setActiveStep] = useState(1);
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [studyFormState, setStudyFormState] = useState<StudyFormState>(initialStudyFormState);
  const [medicationFormState, setMedicationFormState] = useState<MedicationFormState>(initialMedicationFormState);
  const [medicationMode, setMedicationMode] = useState<MedicationMode>("manual");
  const [inventoryMedicationFormState, setInventoryMedicationFormState] =
    useState<InventoryMedicationFormState>(initialInventoryMedicationFormState);
  const [inventoryResults, setInventoryResults] = useState<InventoryItem[]>([]);
  const [selectedInventoryItem, setSelectedInventoryItem] = useState<InventoryItem | null>(null);
  const [isSearchingInventory, setIsSearchingInventory] = useState(false);
  const [inventoryMedicationMessage, setInventoryMedicationMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [areDetailsExpanded, setAreDetailsExpanded] = useState(false);

  const consultationId = consultation?.id ?? null;
  const title =
    consultation?.consultation_type === "follow_up"
      ? "Consulta de control"
      : "Consulta";
  const patientDescription = getPatientDescription(patient);
  const aiPatientContext = useMemo(() => buildAiPatientContext(patient), [patient]);
  const attendingUserName = getTraceableUserName(consultation, "attending");
  const registeredByName = getTraceableUserName(consultation, "created_by");
  const localStorageKeyPrefix = consultationId
    ? `vetclinic:consultation:${consultationId}`
    : null;

  const initializeWorkflow = useCallback(async () => {
    if (hasStartedRef.current) {
      return;
    }

    hasStartedRef.current = true;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      if (props.mode === "new") {
        const historyResponse = await getPatientClinicalHistory(props.patientId);
        const loadedPatient = historyResponse.data.patient;
        setPatient(loadedPatient);

        const draftId = getPatientDraftId(props.patientId);
        if (draftId) {
          try {
            const draftResponse = await getConsultation(draftId);
            if (
              draftResponse.data.patient_id === props.patientId &&
              draftResponse.data.status === "draft"
            ) {
              loadConsultationIntoState(draftResponse.data);
              setIsLoading(false);
              return;
            }
          } catch {
            clearPatientDraftId(props.patientId);
          }
        }

        const draftResponse = await createConsultation({
          patient_id: props.patientId,
          visit_date: new Date().toISOString(),
          reason: "Consulta en borrador",
          status: "draft",
          current_step: 1,
        });
        setPatientDraftId(props.patientId, draftResponse.data.id);
        loadConsultationIntoState(draftResponse.data);
        setIsLoading(false);
        return;
      }

      const consultationResponse = await getConsultation(props.consultationId);
      loadConsultationIntoState(consultationResponse.data);

      try {
        const historyResponse = await getPatientClinicalHistory(
          consultationResponse.data.patient_id,
        );
        setPatient(historyResponse.data.patient);
      } catch {
        setPatient(null);
      }

      setIsLoading(false);
    } catch (error) {
      setIsLoading(false);
      setErrorMessage(getApiErrorMessage(error));
    }
  }, [props]);

  useEffect(() => {
    void initializeWorkflow();
  }, [initializeWorkflow]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    if (toastTimeoutRef.current) {
      window.clearTimeout(toastTimeoutRef.current);
    }

    toastTimeoutRef.current = window.setTimeout(() => {
      setToast(null);
      toastTimeoutRef.current = null;
    }, 5000);

    return () => {
      if (toastTimeoutRef.current) {
        window.clearTimeout(toastTimeoutRef.current);
        toastTimeoutRef.current = null;
      }
    };
  }, [toast]);

  useEffect(() => {
    if (!errorMessage || !consultation) {
      return;
    }

    showToast({
      title: "No fue posible completar la acción",
      detail: errorMessage,
      variant: "error",
    });
    setErrorMessage(null);
  }, [consultation, errorMessage]);

  useEffect(() => {
    if (!localStorageKeyPrefix || isLoading) {
      return;
    }

    saveLocalStep(localStorageKeyPrefix, activeStep, formState);
  }, [activeStep, formState, isLoading, localStorageKeyPrefix]);

  useEffect(() => {
    if (isLoading) {
      previousStepRef.current = activeStep;
      return;
    }

    if (previousStepRef.current === null) {
      previousStepRef.current = activeStep;
      return;
    }

    if (previousStepRef.current === activeStep) {
      return;
    }

    workflowRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    previousStepRef.current = activeStep;
  }, [activeStep, isLoading]);

  useEffect(() => {
    if (medicationMode !== "inventory") {
      return;
    }

    let isCurrent = true;
    const timer = window.setTimeout(async () => {
      setIsSearchingInventory(true);
      setInventoryMedicationMessage(null);

      try {
        const response = await searchInventoryMedications(
          inventoryMedicationFormState.search,
        );
        if (isCurrent) {
          setInventoryResults(response.data);
        }
      } catch (error) {
        if (isCurrent) {
          setInventoryMedicationMessage(getApiErrorMessage(error));
        }
      } finally {
        if (isCurrent) {
          setIsSearchingInventory(false);
        }
      }
    }, 300);

    return () => {
      isCurrent = false;
      window.clearTimeout(timer);
    };
  }, [inventoryMedicationFormState.search, medicationMode]);

  const completedUntil = useMemo(() => {
    const current = consultation?.current_step ?? activeStep;
    return Math.max(0, Math.min(current - 1, steps.length));
  }, [activeStep, consultation?.current_step]);

  function loadConsultationIntoState(nextConsultation: Consultation) {
    const nextStep = clampStep(nextConsultation.current_step ?? 1);
    const baseFormState = toFormState(nextConsultation);
    setConsultation(nextConsultation);
    setActiveStep(nextStep);
    setFormState(mergeLocalSteps(nextConsultation.id, baseFormState));
  }

  function updateField<Key extends keyof FormState>(key: Key, value: FormState[Key]) {
    setFormState((current) => ({ ...current, [key]: value }));
  }

  function showToast(nextToast: ToastState) {
    if (toastTimeoutRef.current) {
      window.clearTimeout(toastTimeoutRef.current);
      toastTimeoutRef.current = null;
    }
    setToast(nextToast);
  }

  function showAiToast(
    title: string,
    detail?: string,
    variant: "success" | "error" = "success",
  ) {
    showToast({ title, detail, variant });
  }

  function renderAiRewriteAction(field: string, key: ClinicalTextField) {
    return (
      <AiClinicalRewriteAction
        field={field}
        text={formState[key]}
        patientContext={aiPatientContext}
        onUseSuggestion={(value) => updateField(key, value)}
        onToast={showAiToast}
      />
    );
  }

  async function saveStep(targetStep = activeStep, status: "draft" | "completed" = "draft") {
    if (!consultation || !localStorageKeyPrefix) {
      return false;
    }

    setIsSaving(true);
    setErrorMessage(null);

    const payload: StepUpdatePayload = {
      ...buildPayload(formState),
      status,
      current_step: targetStep,
    };

    try {
      const response =
        status === "completed"
          ? await updateConsultation(consultation.id, payload)
          : await updateConsultationStep(consultation.id, payload);

      setConsultation(response.data);
      clearLocalStep(localStorageKeyPrefix, activeStep);
      if (targetStep !== activeStep) {
        clearLocalStep(localStorageKeyPrefix, targetStep);
      }
      showToast({
        title: "Progreso guardado",
        detail: `Paso ${targetStep} de 8`,
        variant: "success",
      });
      setIsSaving(false);
      return true;
    } catch {
      saveLocalStep(localStorageKeyPrefix, activeStep, formState);
      showToast({
        title: "Guardado local disponible",
        detail: "Sin conexión estable. Guardamos el avance localmente y podrás intentar de nuevo.",
        variant: "error",
      });
      setIsSaving(false);
      return false;
    }
  }

  async function goToStep(nextStep: number) {
    const safeStep = clampStep(nextStep);
    const saved = await saveStep(safeStep, "draft");
    if (saved) {
      setActiveStep(safeStep);
    }
  }

  async function handleHeaderSave() {
    await saveStep(activeStep, "draft");
  }

  async function handleSaveDraft() {
    await saveStep(activeStep, "draft");
  }

  async function handleCompleteConsultation() {
    if (!consultation) {
      return;
    }

    const saved = await saveStep(8, "completed");
    if (!saved) {
      return;
    }

    clearPatientDraftId(consultation.patient_id);
    clearAllLocalSteps(consultation.id);
    router.push(`/patients/${consultation.patient_id}`);
  }

  async function handleAddStudy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!consultation || !studyFormState.name.trim()) {
      return;
    }

    const payload: CreateStudyRequestPayload = {
      name: studyFormState.name.trim(),
      study_type: studyFormState.study_type,
      notes: studyFormState.notes.trim() || null,
    };

    setIsAddingStudy(true);
    setErrorMessage(null);

    try {
      const response = await createConsultationStudyRequest(consultation.id, payload);
      setConsultation((current) =>
        current
          ? {
              ...current,
              study_requests: [...current.study_requests, response.data],
            }
          : current,
      );
      setStudyFormState(initialStudyFormState);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsAddingStudy(false);
    }
  }

  async function handleDeleteStudy(studyRequest: ConsultationStudyRequest) {
    setErrorMessage(null);
    try {
      await deleteConsultationStudyRequest(studyRequest.id);
      setConsultation((current) =>
        current
          ? {
              ...current,
              study_requests: current.study_requests.filter(
                (item) => item.id !== studyRequest.id,
              ),
            }
          : current,
      );
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    }
  }

  async function handleAddMedication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!consultation || !medicationFormState.medication_name.trim()) {
      return;
    }

    const payload: CreateMedicationPayload = {
      medication_name: medicationFormState.medication_name.trim(),
      dose_or_quantity: medicationFormState.dose_or_quantity.trim() || null,
      instructions: medicationFormState.instructions.trim() || null,
    };

    setIsAddingMedication(true);
    setErrorMessage(null);

    try {
      const response = await createConsultationMedication(consultation.id, payload);
      setConsultation((current) =>
        current
          ? {
              ...current,
              medications: [...current.medications, response.data],
            }
          : current,
      );
      setMedicationFormState(initialMedicationFormState);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsAddingMedication(false);
    }
  }

  async function handleAddInventoryMedication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!consultation || !selectedInventoryItem) {
      setInventoryMedicationMessage("Selecciona un medicamento del inventario.");
      return;
    }

    const quantityUsed = Number(inventoryMedicationFormState.quantity_used);
    const currentStock = Number(selectedInventoryItem.current_stock);

    if (Number.isNaN(quantityUsed) || quantityUsed <= 0) {
      setInventoryMedicationMessage("Ingresa una cantidad mayor a cero.");
      return;
    }

    if (quantityUsed > currentStock) {
      setInventoryMedicationMessage("No hay stock suficiente para esta cantidad.");
      return;
    }

    const payload: CreateMedicationPayload = {
      inventory_item_id: selectedInventoryItem.id,
      medication_name: selectedInventoryItem.name,
      quantity_used: inventoryMedicationFormState.quantity_used,
      dose_or_quantity: inventoryMedicationFormState.dose_or_quantity.trim() || null,
      instructions: inventoryMedicationFormState.instructions.trim() || null,
      supplied_by_clinic: true,
    };

    setIsAddingMedication(true);
    setInventoryMedicationMessage(null);
    setErrorMessage(null);

    try {
      const response = await createConsultationMedication(consultation.id, payload);
      setConsultation((current) =>
        current
          ? {
              ...current,
              medications: [...current.medications, response.data],
            }
          : current,
      );
      setInventoryMedicationFormState(initialInventoryMedicationFormState);
      setSelectedInventoryItem(null);
      const searchResponse = await searchInventoryMedications("");
      setInventoryResults(searchResponse.data);
    } catch (error) {
      if (error instanceof ApiClientError && error.code === "insufficient_stock") {
        setInventoryMedicationMessage(
          "No hay stock suficiente. El inventario pudo haber cambiado.",
        );
        return;
      }

      setInventoryMedicationMessage(getApiErrorMessage(error));
    } finally {
      setIsAddingMedication(false);
    }
  }

  async function handleDeleteMedication(medication: ConsultationMedication) {
    if (
      medication.supplied_by_clinic &&
      !window.confirm(
        "Eliminar este medicamento no restaura el stock. Si necesitas corregir inventario, registra un ajuste.",
      )
    ) {
      return;
    }

    setErrorMessage(null);
    try {
      await deleteConsultationMedication(medication.id);
      setConsultation((current) =>
        current
          ? {
              ...current,
              medications: current.medications.filter(
                (item) => item.id !== medication.id,
              ),
            }
          : current,
      );
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    }
  }

  async function handleDeleteConsultation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!consultation || deleteConfirmation !== "ELIMINAR") {
      return;
    }

    setIsDeleting(true);
    setErrorMessage(null);

    try {
      await deleteConsultation(consultation.id);
      clearPatientDraftId(consultation.patient_id);
      clearAllLocalSteps(consultation.id);
      router.push(`/patients/${consultation.patient_id}`);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
      setIsDeleting(false);
    }
  }

  if (isLoading) {
    return <div className="loading-card" aria-label="Cargando consulta" />;
  }

  if (errorMessage && !consultation) {
    return <div className="error-state">{errorMessage}</div>;
  }

  if (!consultation) {
    return <div className="empty-state">No encontramos esta consulta.</div>;
  }

  const hasAllergies = hasClinicalText(patient?.allergies);
  const hasChronicConditions = hasClinicalText(patient?.chronic_conditions);
  const alertCount = Number(hasAllergies) + Number(hasChronicConditions);

  return (
    <div className="consultation-workflow" ref={workflowRef}>
      {toast ? (
        <div className="consultation-toast-stack" aria-live="polite" aria-atomic="true">
          <div
            className={`consultation-toast consultation-toast--${toast.variant}`}
            role={toast.variant === "error" ? "alert" : "status"}
          >
            <strong>{toast.title}</strong>
            {toast.detail ? <span>{toast.detail}</span> : null}
          </div>
        </div>
      ) : null}

      <section className="consultation-workflow__header">
        <div className="consultation-workflow__topbar">
          <Link
            aria-label="Volver al paciente"
            className="icon-button"
            href={`/patients/${consultation.patient_id}`}
          >
            <ArrowLeft aria-hidden="true" size={20} />
          </Link>
          <div className="consultation-workflow__title">
            <h1>{title}</h1>
          </div>
          <div className="consultation-workflow__toolbar-actions">
            <button
              className="primary-button consultation-workflow__save"
              disabled={isSaving}
              onClick={handleHeaderSave}
              type="button"
            >
              <Save aria-hidden="true" size={17} />
              <span>{isSaving ? "Guardando..." : "Guardar"}</span>
            </button>
            {props.mode === "edit" ? (
              <button
                aria-label="Eliminar consulta"
                className="icon-button consultation-workflow__delete-button"
                onClick={() => setIsDeleteModalOpen(true)}
                title="Eliminar consulta"
                type="button"
              >
                <Trash2 aria-hidden="true" size={17} />
              </button>
            ) : null}
          </div>
        </div>

        <div className="consultation-workflow__meta-row" aria-label="Resumen del paciente">
          <span className="consultation-chip">
            <strong>Paciente</strong>
            {patient?.name ?? "Paciente"}
          </span>
          <span className="consultation-chip">
            <strong>Raza</strong>
            {patientDescription || "No indicada"}
          </span>
          <span className={getStatusClass(consultation.status)}>
            {consultation.status === "completed" ? "Completada" : "Borrador"}
          </span>
          <span className="badge badge--blue">
            {consultation.consultation_type === "follow_up" ? "Control" : "Inicial"}
          </span>
        </div>

        <div className="consultation-workflow__alert-line">
          {hasAllergies ? (
            <span className="consultation-chip consultation-chip--danger">
              <strong>Alergias</strong>
              {patient?.allergies}
            </span>
          ) : null}
          {hasChronicConditions ? (
            <span className="consultation-chip consultation-chip--warning">
              <strong>Condiciones críticas</strong>
              {patient?.chronic_conditions}
            </span>
          ) : null}
          {alertCount === 0 ? (
            <span className="consultation-workflow__quiet-note">Sin alertas registradas</span>
          ) : null}
          <button
            className="consultation-workflow__details-toggle"
            onClick={() => setAreDetailsExpanded((current) => !current)}
            type="button"
          >
            {areDetailsExpanded ? "Ocultar detalles" : "Ver detalles"}
          </button>
        </div>

        {areDetailsExpanded ? (
          <div className="consultation-workflow__details-panel">
            {consultation.consultation_type === "follow_up" &&
            consultation.parent_consultation_id ? (
              <p className="consultation-workflow__context-note">
                Basada en consulta anterior
              </p>
            ) : null}
            {attendingUserName || registeredByName ? (
              <div className="traceability-meta">
                {attendingUserName ? (
                  <span>
                    <strong>Atendido por:</strong> {attendingUserName}
                  </span>
                ) : null}
                {registeredByName ? (
                  <span>
                    <strong>Registrado por:</strong> {registeredByName}
                  </span>
                ) : null}
              </div>
            ) : null}
            {hasAllergies ? (
              <p>
                <strong>Alergias:</strong> {patient?.allergies}
              </p>
            ) : null}
            {hasChronicConditions ? (
              <p>
                <strong>Condiciones críticas:</strong> {patient?.chronic_conditions}
              </p>
            ) : null}
            {props.mode === "new" ? (
              <p className="panel-note">Esta consulta quedará registrada con tu usuario.</p>
            ) : null}
          </div>
        ) : consultation.consultation_type === "follow_up" &&
          consultation.parent_consultation_id ? (
          <p className="consultation-workflow__context-note">
            Basada en consulta anterior
          </p>
        ) : null}

        <nav className="consultation-stepper" aria-label="Pasos de la consulta">
          {steps.map((step) => {
            const isActive = activeStep === step.id;
            const isCompleted = step.id <= completedUntil;
            return (
              <button
                aria-current={isActive ? "step" : undefined}
                aria-label={`Ir a ${step.label}`}
                className={`consultation-stepper__item${
                  isActive ? " consultation-stepper__item--active" : ""
                }${isCompleted ? " consultation-stepper__item--completed" : ""}`}
                key={step.id}
                onClick={() => void goToStep(step.id)}
                title={step.label}
                type="button"
              >
                <span className="consultation-stepper__number">
                  {isCompleted ? <Check aria-hidden="true" size={13} /> : step.id}
                </span>
                <span className="consultation-stepper__icon" aria-hidden="true">
                  {getStepIcon(step.id)}
                </span>
                <span className="sr-only">{step.label}</span>
              </button>
            );
          })}
        </nav>
      </section>

      <section className="consultation-step-card">
        {activeStep === 1 ? renderAnamnesisStep() : null}
        {activeStep === 2 ? renderExamStep() : null}
        {activeStep === 3 ? renderPresumptiveDiagnosisStep() : null}
        {activeStep === 4 ? renderDiagnosticPlanStep() : null}
        {activeStep === 5 ? renderDiagnosticResultsStep() : null}
        {activeStep === 6 ? renderTherapeuticPlanStep() : null}
        {activeStep === 7 ? renderFinalDiagnosisStep() : null}
        {activeStep === 8 ? renderIndicationsStep() : null}
      </section>

      <div
        className={`consultation-workflow__footer${
          activeStep < 8 ? " consultation-workflow__footer--navigation" : ""
        }`}
      >
        <button
          aria-label="Paso anterior"
          className="secondary-button consultation-nav-button consultation-nav-button--previous"
          disabled={activeStep === 1 || isSaving}
          onClick={() => void goToStep(activeStep - 1)}
          type="button"
        >
          <ChevronLeft aria-hidden="true" size={18} />
          <span>Anterior</span>
        </button>

        {activeStep < 8 ? (
          <>
            <p className="consultation-workflow__footer-status" aria-live="polite">
              Paso {activeStep} de 8
            </p>
            <button
              aria-label="Paso siguiente"
              className="primary-button consultation-nav-button consultation-nav-button--next"
              disabled={isSaving}
              onClick={() => void goToStep(activeStep + 1)}
              type="button"
            >
              <span>Siguiente</span>
              <ChevronRight aria-hidden="true" size={18} />
            </button>
          </>
        ) : (
          <div className="consultation-workflow__final-actions">
            <button
              className="secondary-button"
              disabled={isSaving}
              onClick={handleSaveDraft}
              type="button"
            >
              Guardar borrador
            </button>
            <button
              className="primary-button"
              disabled={isSaving}
              onClick={handleCompleteConsultation}
              type="button"
            >
              Completar consulta
            </button>
          </div>
        )}
      </div>

      {isDeleteModalOpen ? renderDeleteModal() : null}
    </div>
  );

  function renderAnamnesisStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 1"
          icon={<Stethoscope aria-hidden="true" size={20} />}
          title="Anamnesis"
          description="Registra el motivo y el contexto clínico inicial."
        />
        <div className="form-grid">
          <label className="field">
            <span>Fecha de consulta</span>
            <input
              required
              type="datetime-local"
              value={formState.visit_date}
              onChange={(event) => updateField("visit_date", event.target.value)}
            />
          </label>
          <label className="field">
            <span>Motivo de consulta *</span>
            <input
              required
              placeholder="Ej. Vómitos, prurito, control..."
              value={formState.reason}
              onChange={(event) => updateField("reason", event.target.value)}
            />
          </label>
        </div>
        <label className="field">
          <FieldLabelWithAiAction
            label="Síntomas"
            action={renderAiRewriteAction("sintomas", "symptoms")}
          />
          <textarea
            rows={3}
            value={formState.symptoms}
            onChange={(event) => updateField("symptoms", event.target.value)}
          />
        </label>
        <div className="form-grid">
          <label className="field">
            <span>Duración de síntomas</span>
            <input
              placeholder="Ej. 2 días"
              value={formState.symptom_duration}
              onChange={(event) => updateField("symptom_duration", event.target.value)}
            />
          </label>
          <label className="field">
            <span>Hábitos y dieta</span>
            <input
              placeholder="Alimentación, ambiente, cambios recientes"
              value={formState.habits_and_diet}
              onChange={(event) => updateField("habits_and_diet", event.target.value)}
            />
          </label>
        </div>
        <label className="field">
          <FieldLabelWithAiAction
            label="Antecedentes relevantes"
            action={renderAiRewriteAction("antecedentes_relevantes", "relevant_history")}
          />
          <textarea
            rows={3}
            value={formState.relevant_history}
            onChange={(event) => updateField("relevant_history", event.target.value)}
          />
        </label>
      </>
    );
  }

  function renderExamStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 2"
          icon={<Stethoscope aria-hidden="true" size={20} />}
          title="Examen"
          description="Signos vitales y hallazgos físicos."
        />
        <div className="consultation-metrics-grid">
          <NumberField
            label="Temperatura °C"
            value={formState.temperature_c}
            onChange={(value) => updateField("temperature_c", value)}
            step="0.1"
          />
          <NumberField
            label="Peso actual kg"
            value={formState.current_weight_kg}
            onChange={(value) => updateField("current_weight_kg", value)}
            step="0.1"
          />
          <NumberField
            label="Frecuencia cardiaca"
            value={formState.heart_rate}
            onChange={(value) => updateField("heart_rate", value)}
          />
          <NumberField
            label="Frecuencia respiratoria"
            value={formState.respiratory_rate}
            onChange={(value) => updateField("respiratory_rate", value)}
          />
        </div>
        <div className="form-grid">
          <label className="field">
            <span>Mucosas</span>
            <select
              value={formState.mucous_membranes}
              onChange={(event) => updateField("mucous_membranes", event.target.value)}
            >
              <option value="">Seleccionar</option>
              {mucousMembraneOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Hidratación</span>
            <select
              value={formState.hydration}
              onChange={(event) => updateField("hydration", event.target.value)}
            >
              <option value="">Seleccionar</option>
              {hydrationOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="field">
          <FieldLabelWithAiAction
            label="Hallazgos del examen físico"
            action={renderAiRewriteAction(
              "hallazgos_examen_fisico",
              "physical_exam_findings",
            )}
          />
          <textarea
            rows={5}
            value={formState.physical_exam_findings}
            onChange={(event) => updateField("physical_exam_findings", event.target.value)}
          />
        </label>
      </>
    );
  }

  function renderPresumptiveDiagnosisStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 3"
          icon={<Stethoscope aria-hidden="true" size={20} />}
          title="Diagnóstico presuntivo"
          description="Hipótesis clínica y etiquetas de orientación."
        />
        <label className="field">
          <FieldLabelWithAiAction
            label="Diagnóstico presuntivo"
            action={renderAiRewriteAction(
              "diagnostico_presuntivo",
              "presumptive_diagnosis",
            )}
          />
          <textarea
            rows={5}
            value={formState.presumptive_diagnosis}
            onChange={(event) => updateField("presumptive_diagnosis", event.target.value)}
          />
        </label>
        <label className="field">
          <span>Etiquetas diagnósticas</span>
          <input
            placeholder="Separar con comas: respiratorio, agudo..."
            value={formState.diagnostic_tags}
            onChange={(event) => updateField("diagnostic_tags", event.target.value)}
          />
        </label>
      </>
    );
  }

  function renderDiagnosticPlanStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 4"
          icon={<FlaskConical aria-hidden="true" size={20} />}
          title="Plan diagnóstico"
          description="Estudios solicitados y notas del plan."
        />
        <form className="consultation-inline-form" onSubmit={handleAddStudy}>
          <div className="form-grid">
            <label className="field">
              <span>Estudio</span>
              <input
                required
                placeholder="Ej. Hemograma"
                value={studyFormState.name}
                onChange={(event) =>
                  setStudyFormState((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Tipo</span>
              <select
                value={studyFormState.study_type}
                onChange={(event) =>
                  setStudyFormState((current) => ({
                    ...current,
                    study_type: event.target.value as ConsultationStudyRequestType,
                  }))
                }
              >
                <option value="laboratory">Laboratorio</option>
                <option value="exam">Examen</option>
                <option value="other">Otro</option>
              </select>
            </label>
          </div>
          <label className="field">
            <span>Notas</span>
            <textarea
              rows={3}
              value={studyFormState.notes}
              onChange={(event) =>
                setStudyFormState((current) => ({
                  ...current,
                  notes: event.target.value,
                }))
              }
            />
          </label>
          <button className="secondary-button" disabled={isAddingStudy} type="submit">
            {isAddingStudy ? "Agregando..." : "Agregar"}
          </button>
        </form>
        <RecordList
          emptyText="No hay estudios solicitados."
          items={consultation?.study_requests ?? []}
          renderItem={(studyRequest) => (
            <RecordRow
              key={studyRequest.id}
              title={studyRequest.name}
              subtitle={`${getStudyTypeLabel(studyRequest.study_type)}${
                studyRequest.notes ? ` · ${studyRequest.notes}` : ""
              }`}
              onDelete={() => void handleDeleteStudy(studyRequest)}
            />
          )}
        />
        <label className="field">
          <FieldLabelWithAiAction
            label="Notas del plan diagnóstico"
            action={renderAiRewriteAction(
              "notas_plan_diagnostico",
              "diagnostic_plan_notes",
            )}
          />
          <textarea
            rows={4}
            value={formState.diagnostic_plan_notes}
            onChange={(event) => updateField("diagnostic_plan_notes", event.target.value)}
          />
        </label>
      </>
    );
  }

  function renderDiagnosticResultsStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 5"
          icon={<FlaskConical aria-hidden="true" size={20} />}
          title="Resultados diagnósticos"
          description="Resumen clínico de los resultados obtenidos."
        />
        <label className="field">
          <FieldLabelWithAiAction
            label="Resultados del plan diagnóstico"
            action={renderAiRewriteAction(
              "resultados_diagnosticos",
              "diagnostic_results",
            )}
          />
          <textarea
            rows={5}
            placeholder="Ej. Hemograma compatible con proceso infeccioso leve. Radiografía sin hallazgos relevantes. Ecografía con signos compatibles con gastritis."
            value={formState.diagnostic_results}
            onChange={(event) => updateField("diagnostic_results", event.target.value)}
          />
          <small>
            Resume aquí los hallazgos más importantes de los estudios realizados.
          </small>
        </label>
      </>
    );
  }

  function renderTherapeuticPlanStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 6"
          icon={<Pill aria-hidden="true" size={20} />}
          title="Plan terapéutico"
          description="Registra medicamentos manuales o descuenta stock desde inventario."
        />
        <div className="choice-grid choice-grid--two consultation-medication-mode">
          <button
            type="button"
            className={`choice-card${medicationMode === "inventory" ? " choice-card--selected" : ""}`}
            onClick={() => setMedicationMode("inventory")}
          >
            <Package size={20} />
            <span>Medicamento de inventario</span>
            <small>Descuenta stock de la clínica</small>
          </button>
          <button
            type="button"
            className={`choice-card${medicationMode === "manual" ? " choice-card--selected" : ""}`}
            onClick={() => setMedicationMode("manual")}
          >
            <Pill size={20} />
            <span>Otro medicamento</span>
            <small>Registro libre sin inventario</small>
          </button>
        </div>

        {medicationMode === "manual" ? (
          <form className="consultation-inline-form" onSubmit={handleAddMedication}>
            <div className="form-grid">
              <label className="field">
                <span>Nombre del medicamento</span>
                <input
                  required
                  placeholder="Nombre del medicamento"
                  value={medicationFormState.medication_name}
                  onChange={(event) =>
                    setMedicationFormState((current) => ({
                      ...current,
                      medication_name: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="field">
                <span>Dosis o cantidad</span>
                <input
                  placeholder="Ej. 250 mg"
                  value={medicationFormState.dose_or_quantity}
                  onChange={(event) =>
                    setMedicationFormState((current) => ({
                      ...current,
                      dose_or_quantity: event.target.value,
                    }))
                  }
                />
              </label>
            </div>
            <label className="field">
              <span>Indicaciones</span>
              <textarea
                rows={3}
                value={medicationFormState.instructions}
                onChange={(event) =>
                  setMedicationFormState((current) => ({
                    ...current,
                    instructions: event.target.value,
                  }))
                }
              />
            </label>
            <button className="secondary-button" disabled={isAddingMedication} type="submit">
              {isAddingMedication ? "Agregando..." : "Agregar medicamento"}
            </button>
          </form>
        ) : (
          <form className="consultation-inline-form" onSubmit={handleAddInventoryMedication}>
            <label className="field">
              <span>Buscar medicamento</span>
              <input
                placeholder="Buscar por nombre o proveedor..."
                value={inventoryMedicationFormState.search}
                onChange={(event) =>
                  setInventoryMedicationFormState((current) => ({
                    ...current,
                    search: event.target.value,
                  }))
                }
              />
            </label>

            <div className="inventory-medication-results">
              {isSearchingInventory ? (
                <div className="loading-card" aria-label="Buscando inventario" />
              ) : null}
              {!isSearchingInventory && inventoryResults.length === 0 ? (
                <div className="empty-state">No hay medicamentos de inventario para mostrar.</div>
              ) : null}
              {!isSearchingInventory
                ? inventoryResults.map((item) => {
                    const isOutOfStock = Number(item.current_stock) <= 0;
                    const isSelected = selectedInventoryItem?.id === item.id;

                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={`inventory-medication-card${
                          isSelected ? " inventory-medication-card--selected" : ""
                        }`}
                        disabled={isOutOfStock}
                        onClick={() => {
                          setSelectedInventoryItem(item);
                          setInventoryMedicationMessage(null);
                        }}
                      >
                        <span className="inventory-medication-card__icon" aria-hidden="true">
                          <Pill size={18} />
                        </span>
                        <span className="inventory-medication-card__body">
                          <strong>{item.name}</strong>
                          <span>
                            {getInventoryCategoryLabel(item.category)} ·{" "}
                            {formatInventoryQuantity(item.current_stock, item.unit)}
                          </span>
                          <span>{formatInventoryCurrency(item.sale_price_ars)}</span>
                        </span>
                        <span className="timeline-card__badges">
                          {isOutOfStock ? (
                            <span className="badge badge--danger">Sin stock</span>
                          ) : item.is_low_stock ? (
                            <span className="badge badge--warning">Bajo stock</span>
                          ) : null}
                        </span>
                      </button>
                    );
                  })
                : null}
            </div>

            {selectedInventoryItem ? (
              <div className="clinical-section inventory-medication-selected">
                <strong>{selectedInventoryItem.name}</strong>
                <span>
                  Disponible:{" "}
                  {formatInventoryQuantity(
                    selectedInventoryItem.current_stock,
                    selectedInventoryItem.unit,
                  )}
                </span>
              </div>
            ) : null}

            <div className="form-grid">
              <label className="field">
                <span>Cantidad usada *</span>
                <input
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  type="number"
                  value={inventoryMedicationFormState.quantity_used}
                  onChange={(event) =>
                    setInventoryMedicationFormState((current) => ({
                      ...current,
                      quantity_used: event.target.value,
                    }))
                  }
                />
                <small>
                  {selectedInventoryItem
                    ? `Disponible: ${formatInventoryQuantity(
                        selectedInventoryItem.current_stock,
                        selectedInventoryItem.unit,
                      )}`
                    : "Selecciona un medicamento para ver stock disponible."}
                </small>
              </label>
              <label className="field">
                <span>Dosis o cantidad visible</span>
                <input
                  placeholder="Ej. 1 comprimido cada 12 horas"
                  value={inventoryMedicationFormState.dose_or_quantity}
                  onChange={(event) =>
                    setInventoryMedicationFormState((current) => ({
                      ...current,
                      dose_or_quantity: event.target.value,
                    }))
                  }
                />
              </label>
            </div>
            <label className="field">
              <span>Indicaciones</span>
              <textarea
                rows={3}
                value={inventoryMedicationFormState.instructions}
                onChange={(event) =>
                  setInventoryMedicationFormState((current) => ({
                    ...current,
                    instructions: event.target.value,
                  }))
                }
              />
            </label>
            {inventoryMedicationMessage ? (
              <div className="error-state">{inventoryMedicationMessage}</div>
            ) : null}
            <button className="secondary-button" disabled={isAddingMedication} type="submit">
              {isAddingMedication ? "Agregando..." : "Agregar desde inventario"}
            </button>
          </form>
        )}
        <RecordList
          emptyText="No hay medicamentos agregados."
          items={consultation?.medications ?? []}
          renderItem={(medication) => (
            <RecordRow
              key={medication.id}
              title={medication.medication_name}
              subtitle={getMedicationSubtitle(medication)}
              badge={medication.supplied_by_clinic ? "Inventario" : "Manual"}
              warning={
                medication.supplied_by_clinic
                  ? "Stock descontado automáticamente"
                  : undefined
              }
              onDelete={() => void handleDeleteMedication(medication)}
            />
          )}
        />
        <label className="field">
          <FieldLabelWithAiAction
            label="Plan terapéutico"
            action={renderAiRewriteAction("plan_terapeutico", "therapeutic_plan")}
          />
          <textarea
            rows={3}
            value={formState.therapeutic_plan}
            onChange={(event) => updateField("therapeutic_plan", event.target.value)}
          />
        </label>
        <label className="field">
          <FieldLabelWithAiAction
            label="Notas del plan terapéutico"
            action={renderAiRewriteAction(
              "notas_plan_terapeutico",
              "therapeutic_plan_notes",
            )}
          />
          <textarea
            rows={4}
            value={formState.therapeutic_plan_notes}
            onChange={(event) => updateField("therapeutic_plan_notes", event.target.value)}
          />
        </label>
      </>
    );
  }

  function renderFinalDiagnosisStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 7"
          icon={<Stethoscope aria-hidden="true" size={20} />}
          title="Diagnóstico final"
          description="Conclusión diagnóstica cuando ya esté disponible."
        />
        <label className="field">
          <FieldLabelWithAiAction
            label="Diagnóstico final"
            action={renderAiRewriteAction("diagnostico_final", "final_diagnosis")}
          />
          <textarea
            rows={5}
            value={formState.final_diagnosis}
            onChange={(event) => updateField("final_diagnosis", event.target.value)}
          />
        </label>
      </>
    );
  }

  function renderIndicationsStep() {
    return (
      <>
        <StepHeading
          eyebrow="Paso 8"
          icon={<CalendarCheck aria-hidden="true" size={20} />}
          title="Indicaciones"
          description="Instrucciones para casa, control y cierre de la consulta."
        />
        <label className="field">
          <FieldLabelWithAiAction
            label="Indicaciones"
            action={renderAiRewriteAction("indicaciones", "indications")}
          />
          <textarea
            rows={5}
            placeholder="Tratamiento en casa, signos de alarma, cuidados, dieta..."
            value={formState.indications}
            onChange={(event) => updateField("indications", event.target.value)}
          />
        </label>
        <div className="form-grid">
          <label className="field">
            <span>Próximo control</span>
            <input
              type="date"
              value={formState.next_control_date}
              onChange={(event) => updateField("next_control_date", event.target.value)}
            />
          </label>
          <label className="consultation-toggle">
            <input
              checked={formState.reminder_requested}
              type="checkbox"
              onChange={(event) =>
                updateField("reminder_requested", event.target.checked)
              }
            />
            <span>Solicitar recordatorio</span>
          </label>
        </div>
        {formState.reminder_requested ? (
          <div className="empty-state">Funcionalidad de recordatorios en desarrollo.</div>
        ) : null}
        <label className="field">
          <FieldLabelWithAiAction
            label="Resumen de consulta"
            action={
              <AiConsultationSummaryAction
                consultation={buildConsultationSummaryPayload(formState, patient)}
                onInsertSummary={(value) => updateField("consultation_summary", value)}
                onToast={showAiToast}
              />
            }
          />
          <textarea
            rows={4}
            value={formState.consultation_summary}
            onChange={(event) => updateField("consultation_summary", event.target.value)}
          />
        </label>
      </>
    );
  }

  function renderDeleteModal() {
    return (
      <div className="modal-backdrop" role="presentation">
        <section
          aria-labelledby="delete-consultation-title"
          aria-modal="true"
          className="bottom-sheet"
          role="dialog"
        >
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Confirmación</p>
              <h2 id="delete-consultation-title">Eliminar consulta</h2>
            </div>
            <button
              aria-label="Cancelar"
              className="icon-button"
              disabled={isDeleting}
              onClick={() => setIsDeleteModalOpen(false)}
              type="button"
            >
              <X aria-hidden="true" size={20} />
            </button>
          </div>
          <p className="alert-box">
            Esta acción eliminará la consulta y sus medicamentos/estudios solicitados
            asociados. Los exámenes registrados se conservarán.
          </p>
          <form className="entity-form" onSubmit={handleDeleteConsultation}>
            <label className="field">
              <span>Escribe ELIMINAR para confirmar</span>
              <input
                value={deleteConfirmation}
                onChange={(event) => setDeleteConfirmation(event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button
                className="secondary-button"
                disabled={isDeleting}
                onClick={() => setIsDeleteModalOpen(false)}
                type="button"
              >
                Cancelar
              </button>
              <button
                className="danger-button"
                disabled={deleteConfirmation !== "ELIMINAR" || isDeleting}
                type="submit"
              >
                {isDeleting ? "Eliminando..." : "Eliminar consulta"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  }
}

function StepHeading({
  icon,
  title,
  description,
}: {
  eyebrow: string;
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="consultation-step-heading">
      <span className="icon-bubble">{icon}</span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
  );
}

function NumberField({
  label,
  value,
  step = "1",
  onChange,
}: {
  label: string;
  value: string;
  step?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        inputMode="decimal"
        min="0"
        step={step}
        type="number"
        value={value}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
      />
    </label>
  );
}

function FieldLabelWithAiAction({
  label,
  action,
}: {
  label: string;
  action: ReactNode;
}) {
  return (
    <span className="field-label-row">
      <span>{label}</span>
      {action}
    </span>
  );
}

function getMedicationSubtitle(medication: ConsultationMedication) {
  const detailParts = [medication.dose_or_quantity, medication.instructions].filter(Boolean);

  if (!medication.supplied_by_clinic) {
    return detailParts.join(" · ");
  }

  const inventoryParts = [
    medication.quantity_used && medication.inventory_unit
      ? `${medication.quantity_used} ${getInventoryUnitLabel(medication.inventory_unit)}`
      : null,
    medication.total_sale_price_ars
      ? `Total: ${formatInventoryCurrency(medication.total_sale_price_ars)}`
      : null,
    ...detailParts,
  ].filter(Boolean);

  return inventoryParts.join(" · ");
}

function RecordList<T>({
  emptyText,
  items,
  renderItem,
}: {
  emptyText: string;
  items: T[];
  renderItem: (item: T) => ReactNode;
}) {
  if (items.length === 0) {
    return <div className="empty-state">{emptyText}</div>;
  }

  return <div className="consultation-record-list">{items.map(renderItem)}</div>;
}

function RecordRow({
  title,
  subtitle,
  badge,
  warning,
  onDelete,
}: {
  title: string;
  subtitle: string;
  badge?: string;
  warning?: string;
  onDelete: () => void;
}) {
  return (
    <article className="consultation-record-row">
      <div>
        <div className="consultation-record-row__title">
          <h3>{title}</h3>
          {badge ? <span className="badge badge--blue">{badge}</span> : null}
        </div>
        {subtitle ? <p>{subtitle}</p> : null}
        {warning ? <small>{warning}</small> : null}
      </div>
      <button
        aria-label={`Eliminar ${title}`}
        className="icon-button"
        onClick={onDelete}
        type="button"
      >
        <Trash2 aria-hidden="true" size={18} />
      </button>
    </article>
  );
}

function toFormState(consultation: Consultation): FormState {
  return {
    visit_date: toDateTimeLocalValue(consultation.visit_date),
    reason: consultation.reason,
    anamnesis: consultation.anamnesis ?? "",
    symptoms: consultation.symptoms ?? "",
    symptom_duration: consultation.symptom_duration ?? "",
    relevant_history: consultation.relevant_history ?? "",
    habits_and_diet: consultation.habits_and_diet ?? "",
    temperature_c: toInputNumber(consultation.temperature_c),
    current_weight_kg: toInputNumber(consultation.current_weight_kg),
    heart_rate: toInputNumber(consultation.heart_rate),
    respiratory_rate: toInputNumber(consultation.respiratory_rate),
    mucous_membranes: consultation.mucous_membranes ?? "",
    hydration: consultation.hydration ?? "",
    physical_exam_findings: consultation.physical_exam_findings ?? "",
    presumptive_diagnosis: consultation.presumptive_diagnosis ?? "",
    diagnostic_tags: consultation.diagnostic_tags?.join(", ") ?? "",
    diagnostic_plan_notes: consultation.diagnostic_plan_notes ?? "",
    diagnostic_results: consultation.diagnostic_results ?? "",
    therapeutic_plan: consultation.therapeutic_plan ?? "",
    therapeutic_plan_notes: consultation.therapeutic_plan_notes ?? "",
    final_diagnosis: consultation.final_diagnosis ?? "",
    indications: consultation.indications ?? "",
    next_control_date: consultation.next_control_date ?? "",
    reminder_requested: consultation.reminder_requested,
    consultation_summary: consultation.consultation_summary ?? "",
  };
}

function buildAiPatientContext(patient: Patient | null): AiPatientContext | null {
  if (!patient) {
    return null;
  }

  return {
    name: patient.name,
    species: patient.species,
    breed: patient.breed,
    sex: patient.sex,
    age: patient.estimated_age,
    weight_kg: parseOptionalNumber(patient.weight_kg),
  };
}

function buildConsultationSummaryPayload(
  formState: FormState,
  patient: Patient | null,
): ConsultationSummaryPayload {
  return {
    patient_name: patient?.name ?? null,
    species: patient?.species ?? null,
    breed: patient?.breed ?? null,
    sex: patient?.sex ?? null,
    age: patient?.estimated_age ?? null,
    weight_kg: parseOptionalNumber(patient?.weight_kg),
    reason: formState.reason.trim() || null,
    anamnesis:
      formState.anamnesis.trim() ||
      joinClinicalParts([
        ["Síntomas", formState.symptoms],
        ["Duración", formState.symptom_duration],
        ["Antecedentes", formState.relevant_history],
        ["Hábitos y dieta", formState.habits_and_diet],
      ]),
    physical_exam:
      formState.physical_exam_findings.trim() ||
      joinClinicalParts([
        ["Temperatura", formState.temperature_c ? `${formState.temperature_c} °C` : ""],
        ["Peso actual", formState.current_weight_kg ? `${formState.current_weight_kg} kg` : ""],
        ["Mucosas", formState.mucous_membranes],
        ["Hidratación", formState.hydration],
      ]),
    presumptive_diagnosis: formState.presumptive_diagnosis.trim() || null,
    diagnostic_plan:
      formState.diagnostic_plan_notes.trim() ||
      formState.diagnostic_results.trim() ||
      null,
    therapeutic_plan:
      joinClinicalParts([
        ["Plan terapéutico", formState.therapeutic_plan],
        ["Notas", formState.therapeutic_plan_notes],
      ]) || null,
    instructions: formState.indications.trim() || null,
  };
}

function buildPayload(formState: FormState): StepUpdatePayload {
  return {
    visit_date: new Date(formState.visit_date).toISOString(),
    reason: formState.reason.trim() || "Consulta en borrador",
    anamnesis: formState.anamnesis.trim() || null,
    symptoms: formState.symptoms.trim() || null,
    symptom_duration: formState.symptom_duration.trim() || null,
    relevant_history: formState.relevant_history.trim() || null,
    habits_and_diet: formState.habits_and_diet.trim() || null,
    temperature_c: toOptionalNumber(formState.temperature_c),
    current_weight_kg: toOptionalNumber(formState.current_weight_kg),
    heart_rate: toOptionalNumber(formState.heart_rate),
    respiratory_rate: toOptionalNumber(formState.respiratory_rate),
    mucous_membranes: formState.mucous_membranes || null,
    hydration: formState.hydration || null,
    physical_exam_findings: formState.physical_exam_findings.trim() || null,
    presumptive_diagnosis: formState.presumptive_diagnosis.trim() || null,
    diagnostic_tags: splitTags(formState.diagnostic_tags),
    diagnostic_plan_notes: formState.diagnostic_plan_notes.trim() || null,
    diagnostic_results: formState.diagnostic_results.trim() || null,
    therapeutic_plan: formState.therapeutic_plan.trim() || null,
    therapeutic_plan_notes: formState.therapeutic_plan_notes.trim() || null,
    final_diagnosis: formState.final_diagnosis.trim() || null,
    indications: formState.indications.trim() || null,
    next_control_date: formState.next_control_date || null,
    consultation_summary: formState.consultation_summary.trim() || null,
    reminder_requested: formState.reminder_requested,
  };
}

function mergeLocalSteps(consultationId: string, baseFormState: FormState) {
  return steps.reduce((currentState, step) => {
    const localStep = readLocalStep(consultationId, step.id);
    return localStep ? { ...currentState, ...localStep } : currentState;
  }, baseFormState);
}

function readLocalStep(consultationId: string, step: number): Partial<FormState> | null {
  if (typeof window === "undefined") {
    return null;
  }

  const rawValue = window.localStorage.getItem(
    `vetclinic:consultation:${consultationId}:step:${step}`,
  );

  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as Partial<FormState>;
  } catch {
    return null;
  }
}

function saveLocalStep(prefix: string, step: number, formState: FormState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    `${prefix}:step:${step}`,
    JSON.stringify(pickStepFields(step, formState)),
  );
}

function clearLocalStep(prefix: string, step: number) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(`${prefix}:step:${step}`);
}

function clearAllLocalSteps(consultationId: string) {
  if (typeof window === "undefined") {
    return;
  }

  steps.forEach((step) => {
    window.localStorage.removeItem(
      `vetclinic:consultation:${consultationId}:step:${step.id}`,
    );
  });
}

function pickStepFields(step: number, formState: FormState): Partial<FormState> {
  const fieldsByStep: Record<number, Array<keyof FormState>> = {
    1: [
      "visit_date",
      "reason",
      "anamnesis",
      "symptoms",
      "symptom_duration",
      "relevant_history",
      "habits_and_diet",
    ],
    2: [
      "temperature_c",
      "current_weight_kg",
      "heart_rate",
      "respiratory_rate",
      "mucous_membranes",
      "hydration",
      "physical_exam_findings",
    ],
    3: ["presumptive_diagnosis", "diagnostic_tags"],
    4: ["diagnostic_plan_notes"],
    5: ["diagnostic_results"],
    6: ["therapeutic_plan", "therapeutic_plan_notes"],
    7: ["final_diagnosis"],
    8: [
      "indications",
      "next_control_date",
      "reminder_requested",
      "consultation_summary",
    ],
  };

  return fieldsByStep[step].reduce<Partial<FormState>>((partialState, field) => {
    return { ...partialState, [field]: formState[field] };
  }, {});
}

function getPatientDraftId(patientId: string) {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(`vetclinic:patient:${patientId}:draft-consultation`);
}

function setPatientDraftId(patientId: string, consultationId: string) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    `vetclinic:patient:${patientId}:draft-consultation`,
    consultationId,
  );
}

function clearPatientDraftId(patientId: string) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(`vetclinic:patient:${patientId}:draft-consultation`);
}

function splitTags(value: string) {
  const tags = value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  return tags.length > 0 ? tags : null;
}

function toOptionalNumber(value: string) {
  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function parseOptionalNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function joinClinicalParts(parts: Array<[string, string]>) {
  const values = parts
    .map(([label, value]) => {
      const text = value.trim();
      return text ? `${label}: ${text}` : null;
    })
    .filter(Boolean);

  return values.length > 0 ? values.join(". ") : null;
}

function toInputNumber(value: number | null) {
  return value === null ? "" : String(value);
}

function toDateTimeLocalValue(date: Date | string) {
  const value = typeof date === "string" ? new Date(date) : date;
  const offsetDate = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
}

function clampStep(step: number) {
  return Math.min(Math.max(step, 1), steps.length);
}

function getPatientDescription(patient: Patient | null) {
  if (!patient) {
    return "";
  }

  return patient.breed ? `${patient.breed}/${patient.species}` : patient.species;
}

function getStatusClass(status: Consultation["status"]) {
  return status === "completed"
    ? "status-pill status-pill--ok"
    : "status-pill status-pill--requested";
}

function getStudyTypeLabel(type: ConsultationStudyRequestType) {
  const labels: Record<ConsultationStudyRequestType, string> = {
    laboratory: "Laboratorio",
    exam: "Examen",
    other: "Otro",
  };
  return labels[type];
}

function hasClinicalText(value: string | null | undefined) {
  return Boolean(value?.trim());
}
