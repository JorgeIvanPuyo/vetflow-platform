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

export type UserTrace = {
  id?: string | null;
  full_name?: string | null;
  email?: string | null;
  display_name?: string | null;
  name?: string | null;
};

export type Patient = {
  id: string;
  tenant_id: string;
  owner_id: string;
  created_by_user_id?: string | null;
  created_by_user?: UserTrace | null;
  created_by_user_full_name?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
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

export type ConsultationStatus = "draft" | "completed";
export type ConsultationType = "initial" | "follow_up";

export type ConsultationMedication = {
  id: string;
  tenant_id: string;
  consultation_id: string;
  medication_name: string;
  dose_or_quantity: string | null;
  instructions: string | null;
  inventory_item_id?: string | null;
  inventory_item_name?: string | null;
  inventory_movement_id?: string | null;
  supplied_by_clinic?: boolean;
  quantity_used?: string | null;
  inventory_unit?: InventoryUnit | null;
  unit_sale_price_ars?: string | null;
  total_sale_price_ars?: string | null;
  created_at: string;
  updated_at: string;
};

export type ConsultationStudyRequestType = "laboratory" | "exam" | "other";

export type ConsultationStudyRequest = {
  id: string;
  tenant_id: string;
  consultation_id: string;
  name: string;
  study_type: ConsultationStudyRequestType;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type Consultation = {
  id: string;
  tenant_id: string;
  patient_id: string;
  consultation_type: ConsultationType;
  parent_consultation_id: string | null;
  created_by_user_id?: string | null;
  attending_user_id?: string | null;
  created_by_user?: UserTrace | null;
  attending_user?: UserTrace | null;
  created_by_user_full_name?: string | null;
  attending_user_full_name?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  attending_user_name?: string | null;
  attending_user_email?: string | null;
  visit_date: string;
  reason: string;
  anamnesis: string | null;
  clinical_exam: string | null;
  presumptive_diagnosis: string | null;
  diagnostic_plan: string | null;
  diagnostic_results: string | null;
  therapeutic_plan: string | null;
  final_diagnosis: string | null;
  indications: string | null;
  status: ConsultationStatus;
  current_step: number | null;
  symptoms: string | null;
  symptom_duration: string | null;
  relevant_history: string | null;
  habits_and_diet: string | null;
  temperature_c: number | null;
  current_weight_kg: number | null;
  heart_rate: number | null;
  respiratory_rate: number | null;
  mucous_membranes: string | null;
  hydration: string | null;
  physical_exam_findings: string | null;
  diagnostic_tags: string[] | null;
  diagnostic_plan_notes: string | null;
  therapeutic_plan_notes: string | null;
  next_control_date: string | null;
  consultation_summary: string | null;
  reminder_requested: boolean;
  medications: ConsultationMedication[];
  study_requests: ConsultationStudyRequest[];
  created_at: string;
  updated_at: string;
};

export type ExamStatus = "requested" | "performed" | "result_loaded";

export type Exam = {
  id: string;
  tenant_id: string;
  patient_id: string;
  consultation_id: string | null;
  requested_by_user_id?: string | null;
  requested_by_user?: UserTrace | null;
  requested_by_user_full_name?: string | null;
  requested_by_user_name?: string | null;
  requested_by_user_email?: string | null;
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
  created_by_user_id?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
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
  created_by_user_id?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  bucket_name?: string | null;
  object_path?: string | null;
  original_filename?: string | null;
  content_type?: string | null;
  size_bytes?: number | null;
  uploaded_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type FileDownloadUrlResponse = {
  download_url: string;
  expires_in_seconds: number;
};

export type ClinicalHistoryTimelineItem = {
  type:
    | "consultation"
    | "exam"
    | "preventive_care"
    | "file_reference"
    | "follow_up";
  id: string;
  date: string;
  title: string;
  summary: string;
  created_by?: UserTrace | null;
  attended_by?: UserTrace | null;
  requested_by?: UserTrace | null;
  assigned_user?: UserTrace | null;
  follow_up_status?: FollowUpStatus | null;
  consultation_type?: ConsultationType | null;
  parent_consultation_id?: string | null;
};

export type ClinicalHistory = {
  patient: Patient;
  consultations: Consultation[];
  exams?: Exam[];
  preventive_care?: PreventiveCare[];
  file_references?: PatientFileReference[];
  follow_ups?: FollowUp[];
  timeline?: ClinicalHistoryTimelineItem[];
  owner?: Owner | null;
};

export type ClinicalHistoryPdfExportPayload = {
  date_from?: string;
  date_to?: string;
  include_patient_data: boolean;
  include_owner_data: boolean;
  include_consultations: boolean;
  include_exams: boolean;
  include_preventive_care: boolean;
  include_file_references: boolean;
  detail_level: "summary" | "full";
};

export type ClinicProfile = {
  id: string;
  name: string;
  display_name: string | null;
  logo_url: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
};

export type UpdateClinicProfilePayload = {
  display_name?: string | null;
  logo_url?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
};

export type ClinicTeamMember = {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
};

export type DashboardPeriod = {
  date_from: string;
  date_to: string;
};

export type DashboardCards = {
  appointments_today: number;
  follow_ups_upcoming: number;
  follow_ups_overdue: number;
  consultations_recent: number;
  preventive_care_upcoming: number;
  files_recent: number;
};

export type DashboardAppointmentItem = {
  id: string;
  title: string;
  appointment_type: AppointmentType;
  status: AppointmentStatus;
  start_at: string;
  end_at: string;
  patient_name?: string | null;
  owner_name?: string | null;
  assigned_user_name?: string | null;
};

export type DashboardFollowUpItem = {
  id: string;
  title: string;
  follow_up_type: FollowUpType;
  status: FollowUpStatus;
  due_at: string;
  patient_name?: string | null;
  owner_name?: string | null;
  assigned_user_name?: string | null;
};

export type DashboardConsultationItem = {
  id: string;
  patient_id: string;
  patient_name?: string | null;
  reason: string;
  status: ConsultationStatus;
  visit_date: string;
  attending_user_name?: string | null;
  created_by_user_name?: string | null;
};

export type DashboardPreventiveCareItem = {
  id: string;
  patient_id: string;
  patient_name?: string | null;
  name: string;
  care_type: PreventiveCareType;
  next_due_at: string;
  created_by_user_name?: string | null;
};

export type DashboardFileItem = {
  id: string;
  patient_id: string;
  patient_name?: string | null;
  name: string;
  file_type: string;
  uploaded_at: string;
  created_by_user_name?: string | null;
};

export type DashboardVeterinarianActivityItem = {
  user_id: string;
  full_name: string;
  email: string;
  appointments_today_count: number;
  consultations_recent_count: number;
  follow_ups_pending_count: number;
};

export type DashboardSummary = {
  period: DashboardPeriod;
  cards: DashboardCards;
  appointments_today: DashboardAppointmentItem[];
  upcoming_follow_ups: DashboardFollowUpItem[];
  overdue_follow_ups: DashboardFollowUpItem[];
  recent_consultations: DashboardConsultationItem[];
  upcoming_preventive_care: DashboardPreventiveCareItem[];
  recent_files: DashboardFileItem[];
  activity_by_veterinarian: DashboardVeterinarianActivityItem[];
};

export type DashboardSummaryFilters = {
  date_from?: string;
  date_to?: string;
  assigned_user_id?: string;
  include_completed?: boolean;
};

export type InventoryCategory =
  | "medication"
  | "vaccine"
  | "supply"
  | "food"
  | "other";

export type InventoryUnit =
  | "unit"
  | "tablet"
  | "capsule"
  | "ampoule"
  | "dose"
  | "pipette"
  | "bottle"
  | "vial"
  | "syringe"
  | "ml"
  | "liter"
  | "gram"
  | "kg"
  | "pair"
  | "box"
  | "package"
  | "other";

export type InventoryStatusFilter =
  | "low_stock"
  | "expiring_soon"
  | "expired"
  | "active"
  | "inactive";

export type InventorySortBy =
  | "name"
  | "current_stock"
  | "expiration_date"
  | "created_at"
  | "updated_at";

export type InventorySortOrder = "asc" | "desc";

export type InventoryItem = {
  id: string;
  tenant_id: string;
  name: string;
  category: InventoryCategory;
  subcategory: string | null;
  unit: InventoryUnit;
  supplier: string | null;
  lot_number: string | null;
  expiration_date: string | null;
  current_stock: string;
  minimum_stock: string;
  purchase_price_ars: string | null;
  profit_margin_percentage: string;
  sale_price_ars: string | null;
  round_sale_price: boolean;
  notes: string | null;
  is_active: boolean;
  is_low_stock: boolean;
  is_expiring_soon: boolean;
  is_expired: boolean;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  created_at: string;
  updated_at: string;
};

export type InventorySummary = {
  total_items: number;
  low_stock_count: number;
  expiring_soon_count: number;
  expired_count: number;
};

export type CreateInventoryItemPayload = {
  name: string;
  category: InventoryCategory;
  subcategory?: string | null;
  unit: InventoryUnit;
  supplier?: string | null;
  lot_number?: string | null;
  expiration_date?: string | null;
  current_stock?: number;
  minimum_stock?: number;
  purchase_price_ars?: number | null;
  profit_margin_percentage?: number;
  sale_price_ars?: number | null;
  round_sale_price?: boolean;
  notes?: string | null;
  is_active?: boolean;
};

export type UpdateInventoryItemPayload = Partial<
  Omit<CreateInventoryItemPayload, "current_stock">
>;

export type InventoryListFilters = {
  q?: string;
  category?: InventoryCategory;
  supplier?: string;
  status?: InventoryStatusFilter;
  page?: number;
  page_size?: number;
  sort_by?: InventorySortBy;
  sort_order?: InventorySortOrder;
};

export type InventoryMovementType = "entry" | "exit" | "adjustment";

export type InventoryExitReason =
  | "sale"
  | "consultation_use"
  | "inventory_adjustment"
  | "expired_discard"
  | "damaged"
  | "other";

export type InventoryMovement = {
  id: string;
  inventory_item_id: string;
  movement_type: InventoryMovementType;
  reason: InventoryExitReason | null;
  quantity: string;
  unit_cost_ars: string | null;
  total_cost_ars: string | null;
  unit_sale_price_ars: string | null;
  total_sale_price_ars: string | null;
  supplier: string | null;
  notes: string | null;
  related_patient_id: string | null;
  related_consultation_id: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  created_at: string;
};

export type CreateInventoryEntryPayload = {
  quantity: number;
  total_cost_ars?: number | null;
  unit_cost_ars?: number | null;
  supplier?: string | null;
  notes?: string | null;
};

export type CreateInventoryExitPayload = {
  quantity: number;
  reason: InventoryExitReason;
  unit_sale_price_ars?: number | null;
  notes?: string | null;
  related_patient_id?: string | null;
  related_consultation_id?: string | null;
};

export type InventoryMovementsFilters = {
  page?: number;
  page_size?: number;
  movement_type?: Extract<InventoryMovementType, "entry" | "exit">;
};

export type AppointmentType =
  | "consultation"
  | "follow_up"
  | "vaccine"
  | "deworming"
  | "exam"
  | "other";

export type AppointmentStatus =
  | "scheduled"
  | "completed"
  | "cancelled"
  | "no_show";

export type Appointment = {
  id: string;
  tenant_id: string;
  patient_id: string | null;
  owner_id: string | null;
  assigned_user_id?: string | null;
  created_by_user_id?: string | null;
  title: string;
  reason: string | null;
  appointment_type: AppointmentType;
  status: AppointmentStatus;
  start_at: string;
  end_at: string;
  notes: string | null;
  patient_name?: string | null;
  owner_name?: string | null;
  assigned_user_name?: string | null;
  assigned_user_email?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateAppointmentPayload = {
  patient_id?: string | null;
  owner_id?: string | null;
  assigned_user_id?: string | null;
  title: string;
  reason?: string | null;
  appointment_type: AppointmentType;
  status?: AppointmentStatus;
  start_at: string;
  end_at: string;
  notes?: string | null;
};

export type UpdateAppointmentPayload = Partial<CreateAppointmentPayload>;

export type AppointmentFilters = {
  date_from?: string;
  date_to?: string;
  assigned_user_id?: string;
  patient_id?: string;
  owner_id?: string;
  status?: AppointmentStatus;
  appointment_type?: AppointmentType;
};

export type FollowUpType =
  | "consultation_control"
  | "vaccine"
  | "deworming"
  | "exam_review"
  | "other";

export type FollowUpStatus =
  | "pending"
  | "scheduled"
  | "completed"
  | "cancelled"
  | "overdue";

export type FollowUpSourceType =
  | "consultation"
  | "preventive_care"
  | "exam"
  | "manual";

export type FollowUp = {
  id: string;
  tenant_id: string;
  patient_id: string;
  owner_id: string | null;
  assigned_user_id?: string | null;
  created_by_user_id?: string | null;
  source_type?: FollowUpSourceType | null;
  source_id?: string | null;
  appointment_id?: string | null;
  title: string;
  description: string | null;
  follow_up_type: FollowUpType;
  status: FollowUpStatus;
  due_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  notes: string | null;
  patient_name?: string | null;
  owner_name?: string | null;
  assigned_user_name?: string | null;
  assigned_user_email?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateFollowUpPayload = {
  patient_id: string;
  owner_id?: string | null;
  assigned_user_id?: string | null;
  title: string;
  description?: string | null;
  follow_up_type: FollowUpType;
  due_at: string;
  notes?: string | null;
  source_type?: FollowUpSourceType | null;
  source_id?: string | null;
  create_appointment?: boolean;
  appointment_duration_minutes?: number;
};

export type UpdateFollowUpPayload = Partial<
  Pick<
    CreateFollowUpPayload,
    | "assigned_user_id"
    | "title"
    | "description"
    | "follow_up_type"
    | "due_at"
    | "notes"
  >
> & {
  status?: FollowUpStatus;
  appointment_id?: string | null;
};

export type FollowUpFilters = {
  date_from?: string;
  date_to?: string;
  patient_id?: string;
  owner_id?: string;
  assigned_user_id?: string;
  status?: FollowUpStatus;
  follow_up_type?: FollowUpType;
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
  status?: ConsultationStatus;
  current_step?: number | null;
  symptoms?: string | null;
  symptom_duration?: string | null;
  relevant_history?: string | null;
  habits_and_diet?: string | null;
  temperature_c?: number | null;
  current_weight_kg?: number | null;
  heart_rate?: number | null;
  respiratory_rate?: number | null;
  mucous_membranes?: string | null;
  hydration?: string | null;
  physical_exam_findings?: string | null;
  diagnostic_tags?: string[] | null;
  diagnostic_plan_notes?: string | null;
  diagnostic_results?: string | null;
  therapeutic_plan_notes?: string | null;
  next_control_date?: string | null;
  consultation_summary?: string | null;
  reminder_requested?: boolean;
};

export type UpdateConsultationPayload = Partial<
  Omit<CreateConsultationPayload, "patient_id">
>;

export type StepUpdatePayload = UpdateConsultationPayload;

export type CreateMedicationPayload = {
  medication_name?: string;
  dose_or_quantity?: string | null;
  instructions?: string | null;
  inventory_item_id?: string;
  quantity_used?: string;
  supplied_by_clinic?: boolean;
};

export type CreateStudyRequestPayload = {
  name: string;
  study_type: ConsultationStudyRequestType;
  notes?: string | null;
};

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
