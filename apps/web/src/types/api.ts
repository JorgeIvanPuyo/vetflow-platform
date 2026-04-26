export type ApiListResponse<T> = {
  data: T[];
  meta: {
    page: number;
    page_size: number;
    total: number;
  };
};

export type ApiItemResponse<T> = {
  data: T;
  meta: Record<string, never>;
};

export type ApiErrorResponse = {
  error: {
    code: string;
    message: string;
  };
};

export type HealthResponse = {
  status: string;
};

export type Owner = {
  id: string;
  tenant_id: string;
  full_name: string;
  document_id: string | null;
  phone: string;
  email: string | null;
  address: string | null;
  created_at: string;
  updated_at: string;
};

export type Patient = {
  id: string;
  tenant_id: string;
  owner_id: string;
  name: string;
  species: string;
  breed: string | null;
  sex: string | null;
  estimated_age: string | null;
  birth_date: string | null;
  weight_kg: string | null;
  allergies: string | null;
  chronic_conditions: string | null;
  created_at: string;
  updated_at: string;
};

export type Consultation = {
  id: string;
  tenant_id: string;
  patient_id: string;
  visit_date: string;
  reason: string;
  anamnesis: string | null;
  clinical_exam: string | null;
  presumptive_diagnosis: string | null;
  diagnostic_plan: string | null;
  therapeutic_plan: string | null;
  final_diagnosis: string | null;
  indications: string | null;
  created_at: string;
  updated_at: string;
};

export type ExamStatus = "requested" | "performed" | "result_loaded";

export type Exam = {
  id: string;
  tenant_id: string;
  patient_id: string;
  consultation_id: string | null;
  exam_type: string;
  status: ExamStatus;
  requested_at: string;
  performed_at: string | null;
  result_summary: string | null;
  result_detail: string | null;
  observations: string | null;
  created_at: string;
  updated_at: string;
};

export type PreventiveCareType = "vaccine" | "deworming" | "other";

export type PreventiveCare = {
  id: string;
  tenant_id: string;
  patient_id: string;
  name: string;
  care_type: PreventiveCareType;
  applied_at: string;
  next_due_at: string | null;
  lot_number: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type PatientFileReference = {
  id: string;
  tenant_id: string;
  patient_id: string;
  name: string;
  file_type: string;
  description: string | null;
  external_url: string | null;
  created_at: string;
  updated_at: string;
};

export type ClinicalHistoryTimelineItem = {
  type: "consultation" | "exam" | "preventive_care" | "file_reference";
  id: string;
  date: string;
  title: string;
  summary: string;
};

export type ClinicalHistory = {
  patient: Patient;
  consultations: Consultation[];
  exams?: Exam[];
  preventive_care?: PreventiveCare[];
  file_references?: PatientFileReference[];
  timeline?: ClinicalHistoryTimelineItem[];
  owner?: Owner | null;
};

export type CreateOwnerPayload = {
  full_name: string;
  phone: string;
  email?: string;
  address?: string;
};

export type UpdateOwnerPayload = Partial<
  Omit<CreateOwnerPayload, "email" | "address">
> & {
  email?: string | null;
  address?: string | null;
};

export type CreatePatientPayload = {
  owner_id: string;
  name: string;
  species: string;
  breed?: string;
  sex?: string;
  estimated_age?: string;
  weight_kg?: number;
  allergies?: string;
  chronic_conditions?: string;
};

export type UpdatePatientPayload = Partial<
  Omit<
    CreatePatientPayload,
    "breed" | "sex" | "estimated_age" | "weight_kg" | "allergies" | "chronic_conditions"
  >
> & {
  breed?: string | null;
  sex?: string | null;
  estimated_age?: string | null;
  weight_kg?: number | null;
  allergies?: string | null;
  chronic_conditions?: string | null;
};

export type CreateConsultationPayload = {
  patient_id: string;
  visit_date: string;
  reason: string;
  anamnesis?: string | null;
  clinical_exam?: string | null;
  presumptive_diagnosis?: string | null;
  diagnostic_plan?: string | null;
  therapeutic_plan?: string | null;
  final_diagnosis?: string | null;
  indications?: string | null;
};

export type UpdateConsultationPayload = Partial<
  Omit<CreateConsultationPayload, "patient_id">
>;

export type CreateExamPayload = {
  patient_id: string;
  consultation_id?: string | null;
  exam_type: string;
  requested_at: string;
  observations?: string | null;
};

export type UpdateExamPayload = {
  status?: ExamStatus;
  performed_at?: string | null;
  result_summary?: string | null;
  result_detail?: string | null;
  observations?: string | null;
};

export type CreatePreventiveCarePayload = {
  name: string;
  care_type: PreventiveCareType;
  applied_at: string;
  next_due_at?: string | null;
  lot_number?: string | null;
  notes?: string | null;
};

export type UpdatePreventiveCarePayload = Partial<CreatePreventiveCarePayload>;

export type CreatePatientFileReferencePayload = {
  name: string;
  file_type: string;
  description?: string | null;
  external_url?: string | null;
};

export type UpdatePatientFileReferencePayload =
  Partial<CreatePatientFileReferencePayload>;

export type SearchResult = {
  type: "owner" | "patient";
  id: string;
  title: string;
  subtitle: string;
  owner_id: string | null;
  patient_id: string | null;
};

export type SearchResponse = {
  data: SearchResult[];
  meta: {
    query: string;
  };
};
