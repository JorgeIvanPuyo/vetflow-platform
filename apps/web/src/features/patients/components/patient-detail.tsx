"use client";

import {
  CalendarDays,
  Cat,
  ChevronDown,
  ClipboardCheck,
  Download,
  Dog,
  Edit,
  ExternalLink,
  FileText,
  FolderOpen,
  History,
  Image as ImageIcon,
  Info,
  PawPrint,
  Plus,
  Stethoscope,
  Syringe,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { ApiClientError, getApiErrorMessage } from "@/lib/api";
import { FollowUpFormModal } from "@/features/follow-ups/components/follow-up-form-modal";
import {
  FollowUpFormState,
  buildFollowUpPayload,
  getDefaultAssignedUserId as getDefaultFollowUpAssignedUserId,
  getFollowUpStatusBadgeClass,
  getFollowUpStatusLabel,
  getFollowUpTypeLabel,
  getInitialFollowUpFormState,
  validateFollowUpForm,
} from "@/features/follow-ups/components/follow-up-helpers";
import { getTraceableUserName, getUserTraceLabel } from "@/lib/user-traceability";
import { exportClinicalHistoryPdf } from "@/services/clinical-history-export";
import { getClinicTeam } from "@/services/clinic";
import { createFollowUpConsultation } from "@/services/consultations";
import {
  createPatientFileReference,
  deletePatientFileReference,
  getFileReferenceDownloadUrl,
  getPatientFileReferences,
  uploadPatientFile,
} from "@/services/file-references";
import { createFollowUp } from "@/services/follow-ups";
import { getOwner, getOwners } from "@/services/owners";
import { deletePatient, getPatientClinicalHistory, updatePatient } from "@/services/patients";
import { createPreventiveCare, getPatientPreventiveCare } from "@/services/preventive-care";
import type {
  ClinicTeamMember,
  ClinicalHistory,
  ClinicalHistoryPdfExportPayload,
  ClinicalHistoryTimelineItem,
  Consultation,
  CreatePatientFileReferencePayload,
  CreatePreventiveCarePayload,
  FollowUp,
  Owner,
  Patient,
  PatientFileReference,
  PreventiveCare,
  PreventiveCareType,
  UpdatePatientPayload,
} from "@/types/api";

type PatientDetailProps = {
  patientId: string;
};

type PatientDetailState = {
  isLoading: boolean;
  isPreventiveSubmitting: boolean;
  isFollowUpSubmitting: boolean;
  isFileSubmitting: boolean;
  isFileUploading: boolean;
  isFileDeleting: boolean;
  isFileOpening: boolean;
  isPdfExporting: boolean;
  isPatientSaving: boolean;
  isPatientDeleting: boolean;
  isFollowUpConsultationCreating: boolean;
  clinicalHistory: ClinicalHistory | null;
  owner: Owner | null;
  owners: Owner[];
  team: ClinicTeamMember[];
  preventiveCare: PreventiveCare[];
  fileReferences: PatientFileReference[];
  errorMessage: string | null;
  successMessage: string | null;
};

type PatientDetailSection = "history" | "info" | "preventive" | "files";
type TimelineFilter =
  | "all"
  | "consultation"
  | "exam"
  | "preventive_care"
  | "file_reference"
  | "follow_up";

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

type FileUploadFormState = {
  name: string;
  file_type: string;
  description: string;
  file: File | null;
};

type PdfExportFormState = {
  date_from: string;
  date_to: string;
  detail_level: "summary" | "full";
  include_patient_data: boolean;
  include_owner_data: boolean;
  include_consultations: boolean;
  include_exams: boolean;
  include_preventive_care: boolean;
  include_file_references: boolean;
};

type PatientEditFormState = {
  owner_id: string;
  name: string;
  species: string;
  breed: string;
  sex: string;
  estimated_age: string;
  weight_kg: string;
  allergies: string;
  chronic_conditions: string;
};

type SpeciesOption = "Canino" | "Felino" | "Otro" | "";

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

const initialFileUploadFormState: FileUploadFormState = {
  name: "",
  file_type: "laboratory",
  description: "",
  file: null,
};

const initialPdfExportFormState: PdfExportFormState = {
  date_from: "",
  date_to: "",
  detail_level: "summary",
  include_patient_data: true,
  include_owner_data: true,
  include_consultations: true,
  include_exams: true,
  include_preventive_care: true,
  include_file_references: true,
};

const initialState: PatientDetailState = {
  isLoading: true,
  isPreventiveSubmitting: false,
  isFollowUpSubmitting: false,
  isFileSubmitting: false,
  isFileUploading: false,
  isFileDeleting: false,
  isFileOpening: false,
  isPdfExporting: false,
  isPatientSaving: false,
  isPatientDeleting: false,
  isFollowUpConsultationCreating: false,
  clinicalHistory: null,
  owner: null,
  owners: [],
  team: [],
  preventiveCare: [],
  fileReferences: [],
  errorMessage: null,
  successMessage: null,
};

const initialPatientEditFormState: PatientEditFormState = {
  owner_id: "",
  name: "",
  species: "",
  breed: "",
  sex: "",
  estimated_age: "",
  weight_kg: "",
  allergies: "",
  chronic_conditions: "",
};

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
  { value: "follow_up", label: "Seguimientos" },
];

const preventiveCareTypeOptions: Array<{ value: PreventiveCareType; label: string }> = [
  { value: "vaccine", label: "Vacuna" },
  { value: "deworming", label: "Desparasitación" },
  { value: "other", label: "Otro" },
];

const fileTypeOptions = [
  { value: "laboratory", label: "Laboratorio" },
  { value: "radiography", label: "Radiografía" },
  { value: "ultrasound", label: "Ecografía" },
  { value: "clinical_photo", label: "Foto clínica" },
  { value: "document", label: "PDF / Documento" },
  { value: "other", label: "Otro" },
];

const allowedClinicalFileExtensions = [".pdf", ".jpg", ".jpeg", ".png", ".webp"];
const allowedClinicalFileTypes = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
];

const pdfExportSectionOptions: Array<{
  key: keyof Pick<
    PdfExportFormState,
    | "include_patient_data"
    | "include_owner_data"
    | "include_consultations"
    | "include_exams"
    | "include_preventive_care"
    | "include_file_references"
  >;
  label: string;
}> = [
  { key: "include_patient_data", label: "Datos del paciente" },
  { key: "include_owner_data", label: "Datos del propietario" },
  { key: "include_consultations", label: "Consultas" },
  { key: "include_exams", label: "Exámenes" },
  { key: "include_preventive_care", label: "Vacunas/desparasitación" },
  { key: "include_file_references", label: "Archivos adjuntos" },
];

const speciesOptions: Array<{ value: Exclude<SpeciesOption, "">; label: string; icon: ReactNode }> = [
  { value: "Canino", label: "Canino", icon: <Dog size={22} /> },
  { value: "Felino", label: "Felino", icon: <Cat size={22} /> },
  { value: "Otro", label: "Otro", icon: <Plus size={22} /> },
];

export function PatientDetail({ patientId }: PatientDetailProps) {
  const router = useRouter();
  const [state, setState] = useState<PatientDetailState>(initialState);
  const [activeSection, setActiveSection] = useState<PatientDetailSection>("history");
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>("all");
  const [isPreventiveModalOpen, setIsPreventiveModalOpen] = useState(false);
  const [isFollowUpModalOpen, setIsFollowUpModalOpen] = useState(false);
  const [isFileModalOpen, setIsFileModalOpen] = useState(false);
  const [isFileUploadModalOpen, setIsFileUploadModalOpen] = useState(false);
  const [isPdfExportModalOpen, setIsPdfExportModalOpen] = useState(false);
  const [fileReferenceToDelete, setFileReferenceToDelete] =
    useState<PatientFileReference | null>(null);
  const [preventiveFormState, setPreventiveFormState] = useState<PreventiveCareFormState>(initialPreventiveCareFormState);
  const [followUpFormState, setFollowUpFormState] =
    useState<FollowUpFormState>(getInitialFollowUpFormState());
  const [fileFormState, setFileFormState] = useState<FileReferenceFormState>(initialFileReferenceFormState);
  const [fileUploadFormState, setFileUploadFormState] =
    useState<FileUploadFormState>(initialFileUploadFormState);
  const [pdfExportFormState, setPdfExportFormState] =
    useState<PdfExportFormState>(initialPdfExportFormState);
  const [isPatientEditOpen, setIsPatientEditOpen] = useState(false);
  const [isPatientDeleteOpen, setIsPatientDeleteOpen] = useState(false);
  const [expandedTimelineItems, setExpandedTimelineItems] = useState<Record<string, boolean>>({});
  const [consultationToCreateControl, setConsultationToCreateControl] =
    useState<ClinicalHistoryTimelineItem | null>(null);
  const [patientEditFormState, setPatientEditFormState] =
    useState<PatientEditFormState>(initialPatientEditFormState);
  const [editSpeciesOption, setEditSpeciesOption] = useState<SpeciesOption>("");
  const [customEditSpecies, setCustomEditSpecies] = useState("");
  const [editHasNoKnownAllergies, setEditHasNoKnownAllergies] = useState(false);
  const [editHasNoKnownChronicConditions, setEditHasNoKnownChronicConditions] =
    useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [fileDeleteConfirmation, setFileDeleteConfirmation] = useState("");
  const [pdfExportError, setPdfExportError] = useState<string | null>(null);

  const loadPatientDetail = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, errorMessage: null }));

    try {
      const [
        historyResponse,
        preventiveResponse,
        fileReferenceResponse,
        ownersResponse,
        teamResponse,
      ] = await Promise.all([
        getPatientClinicalHistory(patientId),
        getPatientPreventiveCare(patientId),
        getPatientFileReferences(patientId),
        getOwners(),
        getClinicTeam(),
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
        owners: ownersResponse.data,
        team: teamResponse.data,
        errorMessage: null,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        clinicalHistory: null,
        owner: null,
        owners: [],
        team: [],
        preventiveCare: [],
        fileReferences: [],
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [patientId]);

  useEffect(() => {
    void loadPatientDetail();
  }, [loadPatientDetail]);

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

  function openFollowUpModal(patient: Patient) {
    setFollowUpFormState({
      ...getInitialFollowUpFormState(new Date()),
      patient_id: patient.id,
      owner_id: patient.owner_id,
      assigned_user_id:
        getDefaultFollowUpAssignedUserId(state.team) || state.team[0]?.id || "",
    });
    setIsFollowUpModalOpen(true);
    setState((current) => ({
      ...current,
      errorMessage: null,
      successMessage: null,
    }));
  }

  function closeFollowUpModal() {
    if (state.isFollowUpSubmitting) {
      return;
    }

    setIsFollowUpModalOpen(false);
  }

  async function handleCreateFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validateFollowUpForm(followUpFormState, {
      teamRequired: state.team.length > 0,
    });
    if (validationMessage) {
      setState((current) => ({
        ...current,
        errorMessage: validationMessage,
        successMessage: null,
      }));
      return;
    }

    setState((current) => ({
      ...current,
      isFollowUpSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await createFollowUp(buildFollowUpPayload(followUpFormState));
      setIsFollowUpModalOpen(false);
      setActiveSection("history");
      setState((current) => ({
        ...current,
        isFollowUpSubmitting: false,
        successMessage: followUpFormState.create_appointment
          ? "Seguimiento y turno programados correctamente."
          : "Seguimiento programado correctamente.",
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isFollowUpSubmitting: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  function openFollowUpConsultationModal(item: ClinicalHistoryTimelineItem) {
    setConsultationToCreateControl(item);
    setState((current) => ({
      ...current,
      errorMessage: null,
      successMessage: null,
    }));
  }

  function closeFollowUpConsultationModal() {
    if (state.isFollowUpConsultationCreating) {
      return;
    }

    setConsultationToCreateControl(null);
  }

  async function handleCreateFollowUpConsultation() {
    if (!consultationToCreateControl) {
      return;
    }

    setState((current) => ({
      ...current,
      isFollowUpConsultationCreating: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      const response = await createFollowUpConsultation(consultationToCreateControl.id);
      router.push(`/consultations/${response.data.id}`);
    } catch {
      setConsultationToCreateControl(null);
      setState((current) => ({
        ...current,
        isFollowUpConsultationCreating: false,
        errorMessage: "No fue posible crear la consulta de control.",
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

  async function handleUploadPatientFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const selectedFile = fileUploadFormState.file;
    const name = fileUploadFormState.name.trim();

    if (!selectedFile) {
      setState((current) => ({
        ...current,
        errorMessage: "Selecciona un archivo clínico para subir.",
        successMessage: null,
      }));
      return;
    }

    if (!name) {
      setState((current) => ({
        ...current,
        errorMessage: "Escribe un nombre para identificar el archivo.",
        successMessage: null,
      }));
      return;
    }

    const validationError = getSelectedFileValidationError(selectedFile);
    if (validationError) {
      setState((current) => ({
        ...current,
        errorMessage: validationError,
        successMessage: null,
      }));
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("name", name);
    formData.append("file_type", fileUploadFormState.file_type);

    const description = fileUploadFormState.description.trim();
    if (description) {
      formData.append("description", description);
    }

    setState((current) => ({
      ...current,
      isFileUploading: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await uploadPatientFile(patientId, formData);
      setFileUploadFormState(initialFileUploadFormState);
      setIsFileUploadModalOpen(false);
      setActiveSection("files");
      setState((current) => ({
        ...current,
        isFileUploading: false,
        successMessage: "Archivo subido correctamente.",
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isFileUploading: false,
        errorMessage: getFileUploadErrorMessage(error),
      }));
    }
  }

  async function handleOpenFileReference(fileReference: PatientFileReference) {
    if (state.isFileOpening) {
      return;
    }

    if (fileReference.object_path) {
      setState((current) => ({
        ...current,
        isFileOpening: true,
        errorMessage: null,
        successMessage: null,
      }));

      try {
        const response = await getFileReferenceDownloadUrl(fileReference.id);
        window.open(response.data.download_url, "_blank", "noopener,noreferrer");
        setState((current) => ({ ...current, isFileOpening: false }));
      } catch (error) {
        setState((current) => ({
          ...current,
          isFileOpening: false,
          errorMessage: getApiErrorMessage(error),
        }));
      }
      return;
    }

    if (fileReference.external_url) {
      window.open(fileReference.external_url, "_blank", "noopener,noreferrer");
      return;
    }

    setState((current) => ({
      ...current,
      errorMessage: "Este registro aún no tiene archivo descargable.",
      successMessage: null,
    }));
  }

  function openFileDeleteModal(fileReference: PatientFileReference) {
    setFileReferenceToDelete(fileReference);
    setFileDeleteConfirmation("");
    setState((current) => ({
      ...current,
      errorMessage: null,
      successMessage: null,
    }));
  }

  function closeFileDeleteModal() {
    if (state.isFileDeleting) {
      return;
    }

    setFileReferenceToDelete(null);
    setFileDeleteConfirmation("");
  }

  async function handleDeleteFileReference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!fileReferenceToDelete || fileDeleteConfirmation !== "ELIMINAR") {
      return;
    }

    setState((current) => ({
      ...current,
      isFileDeleting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await deletePatientFileReference(fileReferenceToDelete.id);
      setFileReferenceToDelete(null);
      setFileDeleteConfirmation("");
      setActiveSection("files");
      setState((current) => ({
        ...current,
        isFileDeleting: false,
        successMessage: "Archivo adjunto eliminado correctamente.",
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isFileDeleting: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  function openPdfExportModal() {
    setPdfExportFormState(initialPdfExportFormState);
    setPdfExportError(null);
    setIsPdfExportModalOpen(true);
    setState((current) => ({
      ...current,
      errorMessage: null,
      successMessage: null,
    }));
  }

  function closePdfExportModal() {
    if (state.isPdfExporting) {
      return;
    }

    setIsPdfExportModalOpen(false);
    setPdfExportError(null);
  }

  function toggleTimelineItem(itemKey: string) {
    setExpandedTimelineItems((current) => ({
      ...current,
      [itemKey]: !current[itemKey],
    }));
  }

  async function handleExportClinicalHistoryPdf(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationError = getPdfExportValidationError(pdfExportFormState);
    if (validationError) {
      setPdfExportError(validationError);
      return;
    }

    const payload: ClinicalHistoryPdfExportPayload = {
      include_patient_data: pdfExportFormState.include_patient_data,
      include_owner_data: pdfExportFormState.include_owner_data,
      include_consultations: pdfExportFormState.include_consultations,
      include_exams: pdfExportFormState.include_exams,
      include_preventive_care: pdfExportFormState.include_preventive_care,
      include_file_references: pdfExportFormState.include_file_references,
      detail_level: pdfExportFormState.detail_level,
    };

    if (pdfExportFormState.date_from) {
      payload.date_from = pdfExportFormState.date_from;
    }
    if (pdfExportFormState.date_to) {
      payload.date_to = pdfExportFormState.date_to;
    }

    setState((current) => ({
      ...current,
      isPdfExporting: true,
      errorMessage: null,
      successMessage: null,
    }));
    setPdfExportError(null);

    try {
      const { blob, filename } = await exportClinicalHistoryPdf(patientId, payload);
      downloadBlob(blob, filename ?? "historia-clinica.pdf");
      setIsPdfExportModalOpen(false);
      setState((current) => ({
        ...current,
        isPdfExporting: false,
        successMessage: "PDF generado correctamente.",
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isPdfExporting: false,
      }));
      setPdfExportError(getPdfExportErrorMessage(error));
    }
  }

  function openPatientEditModal(patient: Patient) {
    setPatientEditFormState(toPatientEditFormState(patient));
    const speciesOption = getSpeciesOption(patient.species);
    setEditSpeciesOption(speciesOption);
    setCustomEditSpecies(speciesOption === "Otro" ? patient.species : "");
    setEditHasNoKnownAllergies(!hasClinicalText(patient.allergies));
    setEditHasNoKnownChronicConditions(!hasClinicalText(patient.chronic_conditions));
    setIsPatientEditOpen(true);
    setState((current) => ({
      ...current,
      errorMessage: null,
      successMessage: null,
    }));
  }

  function closePatientEditModal() {
    if (state.isPatientSaving) {
      return;
    }

    setIsPatientEditOpen(false);
    setPatientEditFormState(initialPatientEditFormState);
    setEditSpeciesOption("");
    setCustomEditSpecies("");
    setEditHasNoKnownAllergies(false);
    setEditHasNoKnownChronicConditions(false);
  }

  function openPatientDeleteModal() {
    setDeleteConfirmation("");
    setIsPatientDeleteOpen(true);
    setState((current) => ({
      ...current,
      errorMessage: null,
      successMessage: null,
    }));
  }

  function closePatientDeleteModal() {
    if (state.isPatientDeleting) {
      return;
    }

    setIsPatientDeleteOpen(false);
    setDeleteConfirmation("");
  }

  async function handleUpdatePatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const species = getSelectedSpecies(
      editSpeciesOption,
      patientEditFormState.species,
      customEditSpecies,
    );

    if (!patientEditFormState.owner_id || !patientEditFormState.name.trim() || !species) {
      setState((current) => ({
        ...current,
        errorMessage: "Completa propietario, nombre y especie para guardar cambios.",
        successMessage: null,
      }));
      return;
    }

    const allergies = normalizeOptionalClinicalText(patientEditFormState.allergies);
    const chronicConditions = normalizeOptionalClinicalText(
      patientEditFormState.chronic_conditions,
    );

    const payload: UpdatePatientPayload = {
      owner_id: patientEditFormState.owner_id,
      name: patientEditFormState.name.trim(),
      species,
      breed: patientEditFormState.breed.trim() || null,
      sex: patientEditFormState.sex.trim() || null,
      estimated_age: patientEditFormState.estimated_age.trim() || null,
      allergies: editHasNoKnownAllergies ? null : allergies,
      chronic_conditions: editHasNoKnownChronicConditions ? null : chronicConditions,
    };

    payload.weight_kg = patientEditFormState.weight_kg.trim()
      ? Number(patientEditFormState.weight_kg)
      : null;

    setState((current) => ({
      ...current,
      isPatientSaving: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await updatePatient(patientId, payload);
      setIsPatientEditOpen(false);
      setPatientEditFormState(initialPatientEditFormState);
      setEditSpeciesOption("");
      setCustomEditSpecies("");
      setEditHasNoKnownAllergies(false);
      setEditHasNoKnownChronicConditions(false);
      setState((current) => ({
        ...current,
        isPatientSaving: false,
        successMessage: "Paciente actualizado correctamente.",
      }));
      await loadPatientDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isPatientSaving: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleDeletePatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (deleteConfirmation !== "ELIMINAR" || state.isPatientDeleting) {
      return;
    }

    setState((current) => ({
      ...current,
      isPatientDeleting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await deletePatient(patientId);
      router.push("/patients");
    } catch (error) {
      setState((current) => ({
        ...current,
        isPatientDeleting: false,
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

  const { patient } = state.clinicalHistory;

  return (
    <div className="page-stack patient-detail-page">
      <section className="detail-hero patient-detail-hero">
        <div className="detail-hero__main patient-detail-hero__main">
          <span className={`pet-avatar pet-avatar--large ${getSexAvatarClass(patient.sex)}`} aria-hidden="true">
            {getSpeciesIcon(patient.species, 22)}
          </span>
          <div>
            <h1>{patient.name}</h1>
            <p>
              {patient.breed ? `${patient.breed} · ` : ""}
              {patient.species}
            </p>
          </div>
        </div>
        <div className="button-row patient-detail-hero__actions">
          <button
            className="primary-button patient-detail-hero__primary-action"
            type="button"
            onClick={() => router.push(`/patients/${patientId}/consultations/new`)}
          >
            <Stethoscope aria-hidden="true" size={16} />
            Nueva consulta
          </button>
          <div className="patient-detail-hero__secondary-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => router.push(`/agenda?patient_id=${patientId}`)}
            >
              <CalendarDays aria-hidden="true" size={15} />
              Agendar turno
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => openFollowUpModal(patient)}
            >
              <ClipboardCheck aria-hidden="true" size={15} />
              Programar seguimiento
            </button>
          </div>
        </div>
      </section>

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

      {isPatientEditOpen ? renderPatientEditModal() : null}
      {isPatientDeleteOpen ? renderPatientDeleteModal(patient.name) : null}
      {isPdfExportModalOpen ? renderPdfExportModal() : null}
      {isPreventiveModalOpen ? renderPreventiveCareModal() : null}
      {isFollowUpModalOpen ? renderFollowUpModal(patient) : null}
      {isFileUploadModalOpen ? renderFileUploadModal() : null}
      {isFileModalOpen ? renderFileReferenceModal() : null}
      {fileReferenceToDelete ? renderFileDeleteModal(fileReferenceToDelete) : null}
      {consultationToCreateControl ? renderFollowUpConsultationModal() : null}
    </div>
  );

  function renderHistorySection(timeline: ClinicalHistoryTimelineItem[]) {
    return (
      <section className="panel patient-detail-section">
        <div className="section-heading section-heading--row history-section-heading">
          <div>
            <h2>Historial completo</h2>
            <p>Consultas, seguimientos, exámenes, vacunas, desparasitación y archivos.</p>
          </div>
          <div className="history-header-actions">
            <label className="compact-filter">
              <span className="sr-only">Filtrar historial</span>
              <select value={timelineFilter} onChange={(event) => setTimelineFilter(event.target.value as TimelineFilter)}>
                {timelineFilters.map((filter) => (
                  <option key={filter.value} value={filter.value}>{filter.label}</option>
                ))}
              </select>
            </label>
            <button className="secondary-button" type="button" onClick={openPdfExportModal}>
              <Download aria-hidden="true" size={18} /> Exportar PDF
            </button>
          </div>
        </div>

        {timeline.length === 0 ? (
          <div className="empty-state">No hay registros para mostrar en este historial.</div>
        ) : (
          <ol className="clinical-timeline">
            {timeline.map((item) => {
              const itemKey = `${item.type}-${item.id}`;
              const isExpanded = Boolean(expandedTimelineItems[itemKey]);
              const href = getTimelineHref(item);

              return (
                <li className={`clinical-timeline__item clinical-timeline__item--${item.type}`} key={itemKey}>
                  <span className="clinical-timeline__dot" aria-hidden="true">
                    {getTimelineIcon(item.type)}
                  </span>
                  <article className={`clinical-timeline__card${isExpanded ? " clinical-timeline__card--expanded" : ""}`}>
                    <div className="timeline-card__summary">
                      <div className="timeline-card__summary-main">
                        <time dateTime={item.date}>{formatDateTime(item.date)}</time>
                        {renderTimelineBadges(item)}
                        <h3>{item.title}</h3>
                      </div>
                      <button
                        aria-expanded={isExpanded}
                        aria-label={isExpanded ? "Contraer registro" : "Expandir registro"}
                        className="timeline-card__toggle"
                        type="button"
                        onClick={() => toggleTimelineItem(itemKey)}
                      >
                        <ChevronDown aria-hidden="true" size={16} />
                      </button>
                    </div>

                    {isExpanded ? (
                      <div className="timeline-card__expanded">
                        <div className="timeline-card__details">
                          {item.summary ? <p>{item.summary}</p> : null}
                          {renderTimelineTraceability(item)}
                        </div>
                        {item.type === "consultation" ? (
                          <div className="timeline-card__actions">
                            <Link
                              className="secondary-button secondary-button--compact"
                              href={`/consultations/${item.id}`}
                            >
                              Ver consulta
                            </Link>
                            <button
                              className="secondary-button secondary-button--compact"
                              onClick={() => openFollowUpConsultationModal(item)}
                              type="button"
                            >
                              Consulta de control
                            </button>
                          </div>
                        ) : href ? (
                          <div className="timeline-card__actions">
                            <Link className="secondary-button secondary-button--compact" href={href}>
                              Ver
                            </Link>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </article>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    );
  }

  function renderInfoSection(patient: Patient) {
    return (
      <section className="panel patient-profile-info-card">
        <div className="patient-profile-info-card__header">
          <div>
            <h2>Información</h2>
            <p>Datos generales del paciente y propietario.</p>
          </div>
          <div className="patient-profile-info-card__actions">
            <button
              aria-label="Editar paciente"
              className="secondary-button"
              onClick={() => openPatientEditModal(patient)}
              type="button"
            >
              <Edit aria-hidden="true" size={16} /> Editar
            </button>
            <button
              aria-label="Eliminar paciente"
              className="secondary-button secondary-button--danger"
              onClick={openPatientDeleteModal}
              type="button"
            >
              <Trash2 aria-hidden="true" size={16} /> Eliminar
            </button>
          </div>
        </div>

        <div className="patient-profile-info-card__content">
          <div className="patient-profile-info-block">
            <h3>Datos del paciente</h3>
            <dl className="patient-profile-info-list">
              <div><dt>Nombre</dt><dd>{patient.name}</dd></div>
              <div><dt>Especie</dt><dd>{patient.species}</dd></div>
              <div><dt>Raza</dt><dd>{patient.breed ?? "No indicado"}</dd></div>
              <div><dt>Sexo</dt><dd>{patient.sex ?? "No indicado"}</dd></div>
              <div><dt>Edad estimada</dt><dd>{patient.estimated_age ?? "No indicado"}</dd></div>
              <div><dt>Peso</dt><dd>{patient.weight_kg ? `${patient.weight_kg} kg` : "No indicado"}</dd></div>
              <div><dt>Alergias</dt><dd>{hasClinicalText(patient.allergies) ? patient.allergies : "Sin registros"}</dd></div>
              <div><dt>Condiciones crónicas</dt><dd>{hasClinicalText(patient.chronic_conditions) ? patient.chronic_conditions : "Sin registros"}</dd></div>
              <div><dt>Fecha de creación</dt><dd>{formatDateTime(patient.created_at)}</dd></div>
            </dl>
          </div>

          <div className="patient-profile-info-block">
            <h3>Propietario</h3>
            {state.owner ? (
              <>
                <dl className="patient-profile-info-list">
                  <div><dt>Nombre</dt><dd>{state.owner.full_name}</dd></div>
                  <div><dt>Teléfono</dt><dd>{state.owner.phone}</dd></div>
                  {state.owner.email ? <div><dt>Correo</dt><dd>{state.owner.email}</dd></div> : null}
                </dl>
                <Link className="secondary-button patient-profile-info-card__owner-link" href={`/owners/${state.owner.id}`}>
                  Ver propietario
                </Link>
              </>
            ) : (
              <div className="empty-state">No hay datos del propietario disponibles.</div>
            )}
          </div>
        </div>
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
                  {getTraceableUserName(record, "created_by") ? (
                    <p className="traceability-meta traceability-meta--compact">
                      <strong>Registrado por:</strong>{" "}
                      {getTraceableUserName(record, "created_by")}
                    </p>
                  ) : null}
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
            <p className="eyebrow">Archivos clínicos</p>
            <h2>Archivos adjuntos</h2>
            <p>Laboratorios, radiografías, fotos clínicas y documentos del paciente.</p>
          </div>
          <div className="detail-action-row">
            <button className="primary-button" type="button" onClick={() => setIsFileUploadModalOpen(true)}>
              <Upload aria-hidden="true" size={18} /> Subir archivo
            </button>
            <button className="secondary-button" type="button" onClick={() => setIsFileModalOpen(true)}>
              <Plus aria-hidden="true" size={18} /> Agregar referencia
            </button>
          </div>
        </div>

        {state.fileReferences.length === 0 ? (
          <div className="empty-state">
            <strong>No hay archivos registrados</strong>
            <span>Sube laboratorios, radiografías, fotos clínicas o documentos PDF.</span>
          </div>
        ) : (
          <div className="record-card-list">
            {state.fileReferences.map((fileReference) => (
              <article className="record-card" key={fileReference.id}>
                <span className="icon-bubble icon-bubble--blue">
                  {getFileReferenceIcon(fileReference)}
                </span>
                <div>
                  <div className="record-card__title-row">
                    <span className="badge badge--blue">
                      {fileReference.object_path ? "Archivo cargado" : "Referencia"}
                    </span>
                  </div>
                  <h3>{fileReference.name}</h3>
                  <p>{getFileTypeLabel(fileReference.file_type)}</p>
                  {fileReference.description ? <p>{fileReference.description}</p> : null}
                  {fileReference.original_filename ? (
                    <p>Archivo original: {fileReference.original_filename}</p>
                  ) : null}
                  {fileReference.size_bytes ? <p>Tamaño: {formatFileSize(fileReference.size_bytes)}</p> : null}
                  {fileReference.uploaded_at ? <p>Subido: {formatDateTime(fileReference.uploaded_at)}</p> : null}
                  {getTraceableUserName(fileReference, "created_by") ? (
                    <p className="traceability-meta traceability-meta--compact">
                      <strong>Registrado por:</strong>{" "}
                      {getTraceableUserName(fileReference, "created_by")}
                    </p>
                  ) : null}
                  {!fileReference.object_path && !fileReference.external_url ? (
                    <p>Referencia sin archivo cargado</p>
                  ) : null}
                  <div className="record-card__actions">
                    <button
                      className="secondary-button"
                      disabled={state.isFileOpening || (!fileReference.object_path && !fileReference.external_url)}
                      type="button"
                      onClick={() => void handleOpenFileReference(fileReference)}
                    >
                      {fileReference.object_path ? (
                        <Download aria-hidden="true" size={16} />
                      ) : (
                        <ExternalLink aria-hidden="true" size={16} />
                      )}
                      Ver / Descargar
                    </button>
                    <button
                      className="secondary-button secondary-button--danger"
                      type="button"
                      onClick={() => openFileDeleteModal(fileReference)}
                    >
                      <Trash2 aria-hidden="true" size={16} /> Eliminar
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    );
  }

  function renderFollowUpModal(patient: Patient) {
    return (
      <FollowUpFormModal
        flowMessage={state.errorMessage}
        formState={followUpFormState}
        isSubmitting={state.isFollowUpSubmitting}
        ownerLocked
        owners={state.owners}
        patientLocked
        patients={[patient]}
        submitLabel="Programar seguimiento"
        team={state.team}
        title="Nuevo seguimiento"
        onClose={closeFollowUpModal}
        onPatientChange={() => undefined}
        onSubmit={handleCreateFollowUp}
        onUpdateForm={setFollowUpFormState}
      />
    );
  }

  function renderPatientEditModal() {
    return (
      <div className="modal-backdrop" role="presentation">
        <section
          aria-labelledby="edit-patient-title"
          aria-modal="true"
          className="bottom-sheet"
          role="dialog"
        >
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Edición</p>
              <h2 id="edit-patient-title">Editar paciente</h2>
            </div>
            <button
              aria-label="Cancelar"
              className="icon-button"
              disabled={state.isPatientSaving}
              onClick={closePatientEditModal}
              type="button"
            >
              <X aria-hidden="true" size={20} />
            </button>
          </div>

          {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

          <form className="entity-form" onSubmit={handleUpdatePatient}>
            <label className="field">
              <span>Propietario</span>
              <select
                required
                value={patientEditFormState.owner_id}
                onChange={(event) =>
                  setPatientEditFormState((current) => ({
                    ...current,
                    owner_id: event.target.value,
                  }))
                }
              >
                <option value="">Selecciona un propietario</option>
                {state.owners.map((owner) => (
                  <option key={owner.id} value={owner.id}>
                    {owner.full_name} · {owner.phone}
                  </option>
                ))}
              </select>
            </label>

            <div className="form-grid">
              <label className="field">
                <span>Nombre</span>
                <input
                  required
                  value={patientEditFormState.name}
                  onChange={(event) =>
                    setPatientEditFormState((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                />
              </label>

              <fieldset className="choice-section">
                <legend>Especie</legend>
                <div className="choice-grid choice-grid--three">
                  {speciesOptions.map((option) => (
                    <button
                      aria-pressed={editSpeciesOption === option.value}
                      className={getChoiceClass(editSpeciesOption === option.value)}
                      key={option.value}
                      onClick={() => {
                        setEditSpeciesOption(option.value);
                        if (option.value === "Otro") {
                          setPatientEditFormState((current) => ({ ...current, species: "" }));
                          setCustomEditSpecies("");
                          return;
                        }

                        setCustomEditSpecies("");
                        setPatientEditFormState((current) => ({
                          ...current,
                          species: option.value,
                        }));
                      }}
                      type="button"
                    >
                      {option.icon}
                      <span>{option.label}</span>
                    </button>
                  ))}
                </div>
              </fieldset>

              {editSpeciesOption === "Otro" ? (
                <label className="field">
                  <span>Especifica la especie</span>
                  <input
                    required
                    value={customEditSpecies}
                    onChange={(event) => {
                      setCustomEditSpecies(event.target.value);
                      setPatientEditFormState((current) => ({
                        ...current,
                        species: event.target.value,
                      }));
                    }}
                  />
                </label>
              ) : null}

              <label className="field">
                <span>Raza</span>
                <input
                  value={patientEditFormState.breed}
                  placeholder="Ej. Labrador, Criollo, Persa"
                  onChange={(event) =>
                    setPatientEditFormState((current) => ({
                      ...current,
                      breed: event.target.value,
                    }))
                  }
                />
              </label>

              <fieldset className="choice-section">
                <legend>Sexo</legend>
                <div className="choice-grid choice-grid--two">
                  {["Macho", "Hembra"].map((sex) => (
                    <button
                      aria-pressed={patientEditFormState.sex === sex}
                      className={getChoiceClass(patientEditFormState.sex === sex)}
                      key={sex}
                      onClick={() =>
                        setPatientEditFormState((current) => ({
                          ...current,
                          sex: current.sex === sex ? "" : sex,
                        }))
                      }
                      type="button"
                    >
                      <span aria-hidden="true">{sex === "Macho" ? "♂" : "♀"}</span>
                      <span>{sex}</span>
                    </button>
                  ))}
                </div>
              </fieldset>

              <label className="field">
                <span>Edad estimada</span>
                <input
                  value={patientEditFormState.estimated_age}
                  placeholder="Ej. 2 años, 8 meses, Adulto"
                  onChange={(event) =>
                    setPatientEditFormState((current) => ({
                      ...current,
                      estimated_age: event.target.value,
                    }))
                  }
                />
              </label>

              <label className="field">
                <span>Peso (kg)</span>
                <input
                  inputMode="decimal"
                  value={patientEditFormState.weight_kg}
                  placeholder="Ej. 12.5"
                  onChange={(event) =>
                    setPatientEditFormState((current) => ({
                      ...current,
                      weight_kg: event.target.value,
                    }))
                  }
                />
              </label>
            </div>

            <div className="clinical-toggle-card">
              <label className="checkbox-row">
                <input
                  checked={editHasNoKnownAllergies}
                  type="checkbox"
                  onChange={(event) => {
                    setEditHasNoKnownAllergies(event.target.checked);
                    if (event.target.checked) {
                      setPatientEditFormState((current) => ({ ...current, allergies: "" }));
                    }
                  }}
                />
                <span>Sin alergias conocidas</span>
              </label>
              {!editHasNoKnownAllergies ? (
                <label className="field">
                  <span>Alergias</span>
                  <textarea
                    rows={2}
                    value={patientEditFormState.allergies}
                    placeholder="Ej. Penicilina, pollo, lácteos"
                    onChange={(event) =>
                      setPatientEditFormState((current) => ({
                        ...current,
                        allergies: event.target.value,
                      }))
                    }
                  />
                </label>
              ) : null}
            </div>

            <div className="clinical-toggle-card">
              <label className="checkbox-row">
                <input
                  checked={editHasNoKnownChronicConditions}
                  type="checkbox"
                  onChange={(event) => {
                    setEditHasNoKnownChronicConditions(event.target.checked);
                    if (event.target.checked) {
                      setPatientEditFormState((current) => ({
                        ...current,
                        chronic_conditions: "",
                      }));
                    }
                  }}
                />
                <span>Sin condiciones crónicas conocidas</span>
              </label>
              {!editHasNoKnownChronicConditions ? (
                <label className="field">
                  <span>Condiciones crónicas</span>
                  <textarea
                    rows={2}
                    value={patientEditFormState.chronic_conditions}
                    placeholder="Ej. Diabetes, dermatitis, epilepsia"
                    onChange={(event) =>
                      setPatientEditFormState((current) => ({
                        ...current,
                        chronic_conditions: event.target.value,
                      }))
                    }
                  />
                </label>
              ) : null}
            </div>

            <div className="modal-actions">
              <button
                className="secondary-button"
                disabled={state.isPatientSaving}
                onClick={closePatientEditModal}
                type="button"
              >
                Cancelar
              </button>
              <button className="primary-button" disabled={state.isPatientSaving} type="submit">
                {state.isPatientSaving ? "Guardando..." : "Guardar cambios"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  }

  function renderPatientDeleteModal(patientName: string) {
    return (
      <div className="modal-backdrop" role="presentation">
        <section
          aria-labelledby="delete-patient-title"
          aria-modal="true"
          className="bottom-sheet"
          role="dialog"
        >
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Acción irreversible</p>
              <h2 id="delete-patient-title">Eliminar paciente</h2>
            </div>
            <button
              aria-label="Cancelar"
              className="icon-button"
              disabled={state.isPatientDeleting}
              onClick={closePatientDeleteModal}
              type="button"
            >
              <X aria-hidden="true" size={20} />
            </button>
          </div>

          <div className="danger-callout" role="alert">
            <strong>{patientName}</strong>
            <span>
              Esta acción eliminará el paciente y toda su información clínica asociada,
              incluyendo consultas, exámenes, vacunas/desparasitación y referencias de
              archivos.
            </span>
            <span>Esta acción no se puede deshacer.</span>
          </div>

          {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

          <form className="entity-form" onSubmit={handleDeletePatient}>
            <label className="field">
              <span>Escribe ELIMINAR para confirmar</span>
              <input
                autoComplete="off"
                value={deleteConfirmation}
                onChange={(event) => setDeleteConfirmation(event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button
                className="secondary-button"
                disabled={state.isPatientDeleting}
                onClick={closePatientDeleteModal}
                type="button"
              >
                Cancelar
              </button>
              <button
                className="danger-button"
                disabled={deleteConfirmation !== "ELIMINAR" || state.isPatientDeleting}
                type="submit"
              >
                {state.isPatientDeleting ? "Eliminando..." : "Confirmar eliminación"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  }

  function renderPdfExportModal() {
    return (
      <div className="modal-backdrop" role="presentation">
        <section
          aria-labelledby="pdf-export-title"
          aria-modal="true"
          className="bottom-sheet"
          role="dialog"
        >
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Historial clínico</p>
              <h2 id="pdf-export-title">Exportar historia clínica</h2>
            </div>
            <button
              aria-label="Cancelar"
              className="icon-button"
              disabled={state.isPdfExporting}
              onClick={closePdfExportModal}
              type="button"
            >
              <X aria-hidden="true" size={20} />
            </button>
          </div>

          <p className="panel-note">Selecciona qué información quieres incluir en el PDF.</p>
          {pdfExportError ? <div className="error-state">{pdfExportError}</div> : null}

          <form className="entity-form" onSubmit={handleExportClinicalHistoryPdf}>
            <fieldset className="choice-section">
              <legend>Rango de fechas</legend>
              <div className="form-grid">
                <label className="field">
                  <span>Desde</span>
                  <input
                    type="date"
                    value={pdfExportFormState.date_from}
                    onChange={(event) =>
                      setPdfExportFormState((current) => ({
                        ...current,
                        date_from: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>Hasta</span>
                  <input
                    type="date"
                    value={pdfExportFormState.date_to}
                    onChange={(event) =>
                      setPdfExportFormState((current) => ({
                        ...current,
                        date_to: event.target.value,
                      }))
                    }
                  />
                </label>
              </div>
            </fieldset>

            <fieldset className="choice-section">
              <legend>Nivel de detalle</legend>
              <div className="choice-grid choice-grid--two">
                <button
                  aria-pressed={pdfExportFormState.detail_level === "summary"}
                  className={getChoiceClass(pdfExportFormState.detail_level === "summary")}
                  type="button"
                  onClick={() =>
                    setPdfExportFormState((current) => ({
                      ...current,
                      detail_level: "summary",
                    }))
                  }
                >
                  <span>Resumen</span>
                  <small>Incluye datos principales.</small>
                </button>
                <button
                  aria-pressed={pdfExportFormState.detail_level === "full"}
                  className={getChoiceClass(pdfExportFormState.detail_level === "full")}
                  type="button"
                  onClick={() =>
                    setPdfExportFormState((current) => ({
                      ...current,
                      detail_level: "full",
                    }))
                  }
                >
                  <span>Completa</span>
                  <small>Incluye detalle clínico extendido.</small>
                </button>
              </div>
            </fieldset>

            <fieldset className="choice-section">
              <legend>Secciones incluidas</legend>
              <div className="checkbox-card-list">
                {pdfExportSectionOptions.map((option) => (
                  <label className="checkbox-row checkbox-row--card" key={option.key}>
                    <input
                      checked={pdfExportFormState[option.key]}
                      type="checkbox"
                      onChange={(event) =>
                        setPdfExportFormState((current) => ({
                          ...current,
                          [option.key]: event.target.checked,
                        }))
                      }
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="modal-actions">
              <button
                className="secondary-button"
                disabled={state.isPdfExporting}
                onClick={closePdfExportModal}
                type="button"
              >
                Cancelar
              </button>
              <button className="primary-button" disabled={state.isPdfExporting} type="submit">
                {state.isPdfExporting ? "Generando PDF..." : "Descargar PDF"}
              </button>
            </div>
          </form>
        </section>
      </div>
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

  function renderFileUploadModal() {
    return (
      <div className="modal-backdrop" role="presentation">
        <section aria-labelledby="file-upload-title" aria-modal="true" className="bottom-sheet" role="dialog">
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Archivos adjuntos</p>
              <h2 id="file-upload-title">Subir archivo</h2>
            </div>
            <button
              aria-label="Cancelar"
              className="icon-button"
              disabled={state.isFileUploading}
              onClick={() => {
                setIsFileUploadModalOpen(false);
                setFileUploadFormState(initialFileUploadFormState);
              }}
              type="button"
            >
              <X aria-hidden="true" size={20} />
            </button>
          </div>

          {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

          <form className="entity-form" onSubmit={handleUploadPatientFile}>
            <label className="field">
              <span>Archivo</span>
              <input
                required
                accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
                type="file"
                onChange={(event) => {
                  const selectedFile = event.target.files?.[0] ?? null;
                  setFileUploadFormState((current) => ({
                    ...current,
                    file: selectedFile,
                    name: current.name || getFilenameWithoutExtension(selectedFile?.name ?? ""),
                  }));
                }}
              />
            </label>

            {fileUploadFormState.file ? (
              <div className="selected-file-summary">
                <span>{fileUploadFormState.file.name}</span>
                <span>{formatFileSize(fileUploadFormState.file.size)}</span>
              </div>
            ) : null}

            <div className="form-grid">
              <label className="field">
                <span>Nombre</span>
                <input
                  required
                  value={fileUploadFormState.name}
                  onChange={(event) => setFileUploadFormState((current) => ({ ...current, name: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Tipo</span>
                <select
                  value={fileUploadFormState.file_type}
                  onChange={(event) => setFileUploadFormState((current) => ({ ...current, file_type: event.target.value }))}
                >
                  {fileTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            </div>

            <label className="field">
              <span>Descripción</span>
              <textarea
                rows={3}
                value={fileUploadFormState.description}
                onChange={(event) => setFileUploadFormState((current) => ({ ...current, description: event.target.value }))}
              />
            </label>

            <div className="modal-actions">
              <button
                className="secondary-button"
                disabled={state.isFileUploading}
                onClick={() => {
                  setIsFileUploadModalOpen(false);
                  setFileUploadFormState(initialFileUploadFormState);
                }}
                type="button"
              >
                Cancelar
              </button>
              <button className="primary-button" disabled={state.isFileUploading} type="submit">
                {state.isFileUploading ? "Subiendo..." : "Subir archivo"}
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

          <p className="panel-note">Registra un enlace externo o una referencia manual cuando el archivo no se subirá a Vetflow.</p>

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

  function renderFileDeleteModal(fileReference: PatientFileReference) {
    return (
      <div className="modal-backdrop" role="presentation">
        <section aria-labelledby="delete-file-title" aria-modal="true" className="bottom-sheet" role="dialog">
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Acción irreversible</p>
              <h2 id="delete-file-title">Eliminar archivo adjunto</h2>
            </div>
            <button
              aria-label="Cancelar"
              className="icon-button"
              disabled={state.isFileDeleting}
              onClick={closeFileDeleteModal}
              type="button"
            >
              <X aria-hidden="true" size={20} />
            </button>
          </div>

          <div className="danger-callout" role="alert">
            <strong>{fileReference.name}</strong>
            <span>
              Esta acción eliminará el archivo adjunto y su registro en la historia clínica.
              Esta acción no se puede deshacer.
            </span>
          </div>

          {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

          <form className="entity-form" onSubmit={handleDeleteFileReference}>
            <label className="field">
              <span>Escribe ELIMINAR para confirmar</span>
              <input
                autoComplete="off"
                value={fileDeleteConfirmation}
                onChange={(event) => setFileDeleteConfirmation(event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button
                className="secondary-button"
                disabled={state.isFileDeleting}
                onClick={closeFileDeleteModal}
                type="button"
              >
                Cancelar
              </button>
              <button
                className="danger-button"
                disabled={fileDeleteConfirmation !== "ELIMINAR" || state.isFileDeleting}
                type="submit"
              >
                {state.isFileDeleting ? "Eliminando..." : "Confirmar eliminación"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  }

  function renderFollowUpConsultationModal() {
    return (
      <div className="modal-backdrop" role="presentation">
        <section
          aria-labelledby="follow-up-consultation-title"
          aria-modal="true"
          className="bottom-sheet"
          role="dialog"
        >
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Consulta</p>
              <h2 id="follow-up-consultation-title">Crear consulta de control</h2>
            </div>
            <button
              aria-label="Cerrar"
              className="icon-button"
              disabled={state.isFollowUpConsultationCreating}
              onClick={closeFollowUpConsultationModal}
              type="button"
            >
              <X aria-hidden="true" size={18} />
            </button>
          </div>
          <p>
            Se creará una nueva consulta basada en esta consulta anterior.
            Podrás editar toda la información antes de guardarla.
          </p>
          <div className="modal-actions">
            <button
              className="secondary-button"
              disabled={state.isFollowUpConsultationCreating}
              onClick={closeFollowUpConsultationModal}
              type="button"
            >
              Cancelar
            </button>
            <button
              className="primary-button"
              disabled={state.isFollowUpConsultationCreating}
              onClick={() => void handleCreateFollowUpConsultation()}
              type="button"
            >
              {state.isFollowUpConsultationCreating
                ? "Creando..."
                : "Crear consulta"}
            </button>
          </div>
        </section>
      </div>
    );
  }
}

function renderTimelineBadges(item: ClinicalHistoryTimelineItem) {
  return (
    <div className="timeline-card__badges">
      <span className={`badge ${getTimelineBadgeClass(item.type)}`}>
        {getTimelineTypeLabel(item.type)}
      </span>
      {item.type === "follow_up" && item.follow_up_status ? (
        <span className={getFollowUpStatusBadgeClass(item.follow_up_status)}>
          {getFollowUpStatusLabel(item.follow_up_status)}
        </span>
      ) : null}
      {item.type === "consultation" ? (
        <span className="badge badge--blue">
          {item.consultation_type === "follow_up" ? "Control" : "Inicial"}
        </span>
      ) : null}
    </div>
  );
}

function renderTimelineContent(item: ClinicalHistoryTimelineItem, isNavigable: boolean) {
  return (
    <>
      {renderTimelineBadges(item)}
      <time dateTime={item.date}>{formatDateTime(item.date)}</time>
      <h3>{item.title}</h3>
      <p>{item.summary}</p>
      {renderTimelineTraceability(item)}
      {isNavigable ? <span className="inline-link">Ver</span> : null}
    </>
  );
}

function renderTimelineTraceability(item: ClinicalHistoryTimelineItem) {
  const traceabilityLines = getTimelineTraceabilityLines(item);

  if (traceabilityLines.length === 0) {
    return null;
  }

  return (
    <div className="traceability-meta traceability-meta--timeline">
      {traceabilityLines.map((line) => (
        <span key={`${line.label}-${line.value}`}>
          <strong>{line.label}:</strong> {line.value}
        </span>
      ))}
    </div>
  );
}

function getTimelineTraceabilityLines(item: ClinicalHistoryTimelineItem) {
  const createdBy = getUserTraceLabel(item.created_by);
  const attendedBy = getUserTraceLabel(item.attended_by);
  const requestedBy = getUserTraceLabel(item.requested_by);
  const assignedUser = getUserTraceLabel(item.assigned_user);

  if (item.type === "consultation") {
    const lines: Array<{ label: string; value: string }> = [];

    if (attendedBy) {
      lines.push({ label: "Atendido por", value: attendedBy });
    }
    if (createdBy && createdBy !== attendedBy) {
      lines.push({ label: "Registrado por", value: createdBy });
    }

    return lines;
  }

  if (item.type === "exam" && requestedBy) {
    return [{ label: "Solicitado por", value: requestedBy }];
  }

  if ((item.type === "preventive_care" || item.type === "file_reference") && createdBy) {
    return [{ label: "Registrado por", value: createdBy }];
  }

  if (item.type === "follow_up") {
    const lines: Array<{ label: string; value: string }> = [];

    if (assignedUser) {
      lines.push({ label: "Veterinario asignado", value: assignedUser });
    }
    if (createdBy && createdBy !== assignedUser) {
      lines.push({ label: "Registrado por", value: createdBy });
    }

    return lines;
  }

  return [];
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
  const consultationsById = new Map(
    clinicalHistory.consultations.map((consultation) => [consultation.id, consultation]),
  );

  if (clinicalHistory.timeline) {
    const followUpsById = new Map(
      (clinicalHistory.follow_ups ?? []).map((followUp) => [followUp.id, followUp]),
    );

    return clinicalHistory.timeline.map((item) => ({
      ...item,
      follow_up_status:
        item.type === "follow_up" ? followUpsById.get(item.id)?.status ?? null : null,
      consultation_type:
        item.type === "consultation"
          ? consultationsById.get(item.id)?.consultation_type ?? "initial"
          : undefined,
      parent_consultation_id:
        item.type === "consultation"
          ? consultationsById.get(item.id)?.parent_consultation_id ?? null
          : undefined,
    }));
  }

  return clinicalHistory.consultations.map((consultation) => ({
    type: "consultation",
    id: consultation.id,
    date: consultation.visit_date,
    title: consultation.reason,
    summary: getConsultationSummary(consultation),
    consultation_type: consultation.consultation_type,
    parent_consultation_id: consultation.parent_consultation_id,
    created_by: getTraceableUserName(consultation, "created_by")
      ? {
          full_name: getTraceableUserName(consultation, "created_by"),
        }
      : null,
    attended_by: getTraceableUserName(consultation, "attending")
      ? {
          full_name: getTraceableUserName(consultation, "attending"),
        }
      : null,
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
  if (item.type === "follow_up") {
    return `/follow-ups/${item.id}`;
  }
  return null;
}

function getTimelineIcon(type: ClinicalHistoryTimelineItem["type"]) {
  if (type === "consultation") return <Stethoscope size={18} />;
  if (type === "exam") return <FileText size={18} />;
  if (type === "preventive_care") return <Syringe size={18} />;
  if (type === "follow_up") return <ClipboardCheck size={18} />;
  return <FolderOpen size={18} />;
}

function getTimelineTypeLabel(type: ClinicalHistoryTimelineItem["type"]) {
  const labels = {
    consultation: "Consulta",
    exam: "Examen",
    preventive_care: "Vacuna/desparasitación",
    file_reference: "Archivo",
    follow_up: "Seguimiento",
  };
  return labels[type];
}

function getTimelineBadgeClass(type: ClinicalHistoryTimelineItem["type"]) {
  if (type === "exam" || type === "file_reference") return "badge--blue";
  if (type === "follow_up") return "badge--warning";
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

function getFileReferenceIcon(fileReference: PatientFileReference) {
  if (fileReference.content_type?.startsWith("image/")) {
    return <ImageIcon size={20} />;
  }

  if (fileReference.file_type === "clinical_photo") {
    return <ImageIcon size={20} />;
  }

  return <FileText size={20} />;
}

function formatFileSize(sizeBytes: number) {
  if (sizeBytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(sizeBytes / 1024))} KB`;
  }

  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFilenameWithoutExtension(filename: string) {
  const lastDotIndex = filename.lastIndexOf(".");
  if (lastDotIndex <= 0) {
    return filename;
  }

  return filename.slice(0, lastDotIndex);
}

function getSelectedFileValidationError(file: File) {
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  const hasValidExtension = allowedClinicalFileExtensions.includes(extension);
  const hasValidType = allowedClinicalFileTypes.includes(file.type);

  if (!hasValidExtension || !hasValidType) {
    return "Tipo de archivo no permitido. Usa PDF, JPG, PNG o WEBP.";
  }

  return null;
}

function getPdfExportValidationError(formState: PdfExportFormState) {
  if (formState.date_from && formState.date_to && formState.date_from > formState.date_to) {
    return "La fecha Desde debe ser anterior o igual a la fecha Hasta.";
  }

  if (!hasSelectedPdfExportSection(formState)) {
    return "Selecciona al menos una sección para incluir en el PDF.";
  }

  return null;
}

function hasSelectedPdfExportSection(formState: PdfExportFormState) {
  return pdfExportSectionOptions.some((option) => formState[option.key]);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function getPdfExportErrorMessage(error: unknown) {
  if (error instanceof ApiClientError && error.code === "invalid_date_range") {
    return "El rango de fechas no es válido.";
  }

  return getApiErrorMessage(error);
}

function getFileUploadErrorMessage(error: unknown) {
  if (error instanceof ApiClientError) {
    if (error.code === "invalid_file_type") {
      return "Tipo de archivo no permitido. Usa PDF, JPG, PNG o WEBP.";
    }
    if (error.code === "file_too_large") {
      return "El archivo supera el tamaño máximo permitido.";
    }
    if (error.code === "missing_file") {
      return "Selecciona un archivo clínico para subir.";
    }
    if (error.code === "storage_not_configured") {
      return "El almacenamiento de archivos aún no está configurado.";
    }
  }

  return getApiErrorMessage(error);
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

function toPatientEditFormState(patient: Patient): PatientEditFormState {
  return {
    owner_id: patient.owner_id,
    name: patient.name,
    species: patient.species,
    breed: patient.breed ?? "",
    sex: patient.sex ?? "",
    estimated_age: patient.estimated_age ?? "",
    weight_kg: patient.weight_kg ?? "",
    allergies: patient.allergies ?? "",
    chronic_conditions: patient.chronic_conditions ?? "",
  };
}

function getSpeciesOption(species: string): SpeciesOption {
  const normalized = species.trim().toLowerCase();
  if (["canino", "perro", "dog", "canine"].some((word) => normalized.includes(word))) {
    return "Canino";
  }
  if (["felino", "gato", "cat", "feline"].some((word) => normalized.includes(word))) {
    return "Felino";
  }
  return "Otro";
}

function getChoiceClass(isSelected: boolean) {
  return isSelected ? "choice-card choice-card--selected" : "choice-card";
}

function getSelectedSpecies(
  selectedSpeciesOption: SpeciesOption,
  species: string,
  customSpecies: string,
) {
  return selectedSpeciesOption === "Otro" ? customSpecies.trim() : species.trim();
}

function normalizeOptionalClinicalText(value: string) {
  const normalized = value.trim();

  if (!normalized || isNoneValue(normalized)) {
    return null;
  }

  return normalized;
}

function hasClinicalText(value: string | null) {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return Boolean(normalized && !isNoneValue(normalized));
}

function isNoneValue(value: string) {
  const normalized = value.trim().toLowerCase();
  return ["ninguna", "ninguno", "no", "n/a", "na", "sin alergias", "sin condiciones"].includes(
    normalized,
  );
}
