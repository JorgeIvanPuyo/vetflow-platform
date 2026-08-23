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
  photo_url?: string | null;
  photo_original_filename?: string | null;
  photo_content_type?: string | null;
  photo_size_bytes?: number | null;
  photo_uploaded_at?: string | null;
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
  ai_summary?: string | null;
  ai_summary_generated_at?: string | null;
  ai_summary_model?: string | null;
  reminder_requested: boolean;
  medications: ConsultationMedication[];
  study_requests: ConsultationStudyRequest[];
  created_at: string;
  updated_at: string;
};

export type ConsultationListItem = {
  id: string;
  patient_id: string;
  patient_name: string;
  owner_id: string;
  owner_name: string;
  visit_date: string;
  reason: string;
  status: ConsultationStatus;
  attending_user_id: string | null;
  attending_user_name: string | null;
  created_by_user_id: string | null;
  created_by_user_name: string | null;
  final_diagnosis: string | null;
  presumptive_diagnosis: string | null;
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
  ai_summary?: string | null;
  ai_summary_generated_at?: string | null;
  ai_summary_model?: string | null;
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
  page_size?: "letter" | "a4" | "legal";
  include_patient_data: boolean;
  include_owner_data: boolean;
  include_consultations: boolean;
  include_consultation_exam_data?: boolean;
  include_exams: boolean;
  include_preventive_care: boolean;
  include_file_references: boolean;
  detail_level: "summary" | "full";
};

export type AiPatientContext = {
  name?: string | null;
  species?: string | null;
  breed?: string | null;
  sex?: string | null;
  age?: string | null;
  weight_kg?: number | null;
};

export type RewriteClinicalNoteRequest = {
  field: string;
  text: string;
  patient_context?: AiPatientContext | null;
};

export type RewriteClinicalNoteResponse = {
  suggestion: string;
  disclaimer?: string;
};

export type ConsultationSummaryPayload = {
  patient_name?: string | null;
  species?: string | null;
  breed?: string | null;
  sex?: string | null;
  age?: string | null;
  weight_kg?: number | null;
  reason?: string | null;
  anamnesis?: string | null;
  physical_exam?: string | null;
  presumptive_diagnosis?: string | null;
  diagnostic_plan?: string | null;
  therapeutic_plan?: string | null;
  instructions?: string | null;
};

export type GenerateConsultationSummaryRequest = {
  consultation: ConsultationSummaryPayload;
  summary_type?: "clinical" | "owner_friendly";
};

export type GenerateConsultationSummaryResponse = {
  summary: string;
  disclaimer?: string;
};

export type ConsultationAiSummaryResponse = {
  consultation_id: string;
  summary: string;
  generated_at: string;
  model: string;
  disclaimer: string;
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

export type UpdateClinicTeamMemberPayload = {
  full_name: string;
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
  | "accessory"
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

export type InventoryStockStatus =
  | "in_stock"
  | "low_stock"
  | "out_of_stock"
  | "negative";

export type InventorySortBy =
  | "name"
  | "current_stock"
  | "internal_code"
  | "sale_price_ars"
  | "updated_at";

export type InventorySortOrder = "asc" | "desc";

export type InventoryItem = {
  id: string;
  tenant_id: string;
  internal_code: string;
  name: string;
  category: InventoryCategory;
  subcategory: string | null;
  brand: string | null;
  unit: InventoryUnit;
  supplier: string | null;
  lot_number: string | null;
  expiration_date: string | null;
  current_stock: string;
  minimum_stock: string;
  purchase_price_ars: string | null;
  purchase_tax_rate_percentage?: string | number | null;
  purchase_tax_amount_ars?: string | number | null;
  purchase_price_with_tax_ars?: string | number | null;
  profit_margin_percentage: string;
  sale_price_ars: string | null;
  sale_tax_rate_percentage?: string | number | null;
  sale_tax_amount_ars?: string | number | null;
  sale_price_with_tax_ars?: string | number | null;
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

export type InventoryDashboardAlertType =
  | "negative_stock"
  | "out_of_stock"
  | "low_stock"
  | "inactive_with_stock"
  | "missing_purchase_cost"
  | "missing_sale_price"
  | "missing_brand"
  | "missing_supplier";

export type InventoryDashboardAlertPriority = "critical" | "high" | "medium" | "info";

export type InventoryDashboardFilters = {
  category?: InventoryCategory | null;
  brand?: string | null;
  supplier?: string | null;
  is_active?: boolean | null;
  date_from?: string | null;
  date_to?: string | null;
};

export type InventoryDashboard = {
  generated_at: string;
  filters: {
    category: InventoryCategory | null;
    brand: string | null;
    supplier: string | null;
    is_active: boolean | null;
    date_from: string;
    date_to: string;
  };
  indicators: {
    total_products: number;
    active_products: number;
    inactive_products: number;
    in_stock_products: number;
    low_stock_products: number;
    out_of_stock_products: number;
    negative_stock_products: number;
  };
  valuation: {
    estimated_cost_value_ars: string;
    estimated_sale_value_ars: string;
    includes_negative_stock: boolean;
    disclaimer: string;
  };
  movement_metrics: {
    total_movements: number;
    entry_movements: number;
    exit_movements: number;
    adjustment_movements: number;
    reversal_movements: number;
    clinical_consumption_movements: number;
  };
  alerts: Array<{
    alert_type: InventoryDashboardAlertType;
    priority: InventoryDashboardAlertPriority;
    count: number;
    label: string;
  }>;
  attention_items: Array<{
    id: string;
    internal_code: string;
    name: string;
    category: InventoryCategory;
    current_stock: string;
    minimum_stock: string;
    sale_price_ars: string | null;
    alerts: InventoryDashboardAlertType[];
    priority: InventoryDashboardAlertPriority;
  }>;
  activity: {
    recent_movements: InventoryMovement[];
    recent_imports: InventoryImportListItem[];
    recent_bulk_operations: InventoryBulkOperationListItem[];
  };
};

export type InventoryFilterOptions = {
  brands: string[];
  suppliers: string[];
};

export type CreateInventoryItemPayload = {
  name: string;
  category: InventoryCategory;
  subcategory?: string | null;
  brand?: string | null;
  unit: InventoryUnit;
  supplier?: string | null;
  lot_number?: string | null;
  expiration_date?: string | null;
  minimum_stock?: number;
  purchase_price_ars?: number | null;
  purchase_tax_rate_percentage?: number;
  profit_margin_percentage?: number;
  sale_price_ars?: number | null;
  sale_tax_rate_percentage?: number;
  round_sale_price?: boolean;
  notes?: string | null;
  is_active?: boolean;
};

export type UpdateInventoryItemPayload = Partial<CreateInventoryItemPayload>;

export type InventoryListFilters = {
  search?: string;
  q?: string;
  category?: InventoryCategory;
  brand?: string;
  supplier?: string;
  status?: InventoryStatusFilter;
  stock_status?: InventoryStockStatus;
  is_active?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: InventorySortBy;
  sort_direction?: InventorySortOrder;
  sort_order?: InventorySortOrder;
};

export type InventoryMovementType =
  | "initial_stock"
  | "manual_entry"
  | "manual_exit"
  | "purchase"
  | "sale"
  | "clinical_consumption"
  | "customer_return"
  | "supplier_return"
  | "adjustment_in"
  | "adjustment_out"
  | "expiration"
  | "loss"
  | "breakage"
  | "transfer_in"
  | "transfer_out"
  | "reversal"
  | "entry"
  | "exit"
  | "adjustment";

export type InventoryReversalStatus = "all" | "active" | "reversed" | "reversal";

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
  inventory_item_name?: string | null;
  inventory_item_internal_code?: string | null;
  movement_type: InventoryMovementType;
  reason: string | null;
  quantity: string;
  unit: InventoryUnit | string | null;
  stock_before: string | null;
  stock_after: string | null;
  source_type: string | null;
  source_id: string | null;
  operation_id: string | null;
  reverses_movement_id: string | null;
  reversed_by_movement_id: string | null;
  reversal_status: InventoryReversalStatus;
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

export type InventoryMovementDetail = InventoryMovement & {
  can_be_reversed: boolean;
  reversal_block_reason: string | null;
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
  search?: string;
  inventory_item_id?: string;
  movement_type?: InventoryMovementType;
  created_by_user_id?: string;
  source_type?: string;
  source_id?: string;
  operation_id?: string;
  reversal_status?: InventoryReversalStatus;
  date_from?: string;
  date_to?: string;
  sort_direction?: InventorySortOrder;
};

export type ReverseInventoryMovementPayload = {
  reason: string;
  notes?: string | null;
};

export type InventoryExportMode = "all" | "filtered" | "selected";

export type InventoryExportFilters = {
  search?: string | null;
  category?: InventoryCategory | null;
  brand?: string | null;
  supplier?: string | null;
  stock_status?: InventoryStockStatus | null;
  is_active?: boolean | null;
  sort_by?: InventorySortBy | null;
  sort_direction?: InventorySortOrder | null;
};

export type InventoryExportPayload = {
  mode: InventoryExportMode;
  filters?: InventoryExportFilters | null;
  selected_ids?: string[];
};

export type InventoryBulkOperationType =
  | "increase_sale_price_percentage"
  | "decrease_sale_price_percentage"
  | "set_profit_margin_percentage"
  | "set_sale_price"
  | "set_brand"
  | "set_supplier"
  | "set_minimum_stock"
  | "activate"
  | "deactivate";
export type InventoryBulkSelectionMode = "selected" | "filtered";
export type InventoryBulkOperationStatus =
  | "preview"
  | "confirmed"
  | "partially_reversed"
  | "reversed"
  | "failed"
  | "expired";
export type InventoryBulkOperationItemStatus =
  | "pending"
  | "changed"
  | "unchanged"
  | "invalid"
  | "conflict"
  | "reverted"
  | "excluded";

export type InventoryBulkOperationFilters = {
  search?: string | null;
  category?: InventoryCategory | null;
  brand?: string | null;
  supplier?: string | null;
  stock_status?: InventoryStockStatus | null;
  is_active?: boolean | null;
};

export type InventoryBulkSelectionPayload = {
  selection_mode: InventoryBulkSelectionMode;
  selected_ids?: string[];
  filters?: InventoryBulkOperationFilters | null;
  excluded_ids?: string[];
};

export type InventoryBulkOperationValuePayload = {
  operation_type: InventoryBulkOperationType;
  percentage?: number | null;
  sale_price_ars?: number | null;
  profit_margin_percentage?: number | null;
  brand?: string | null;
  supplier?: string | null;
  minimum_stock?: number | null;
  confirm_clear?: boolean;
};

export type InventoryBulkOperationPreviewPayload = {
  selection: InventoryBulkSelectionPayload;
  operation: InventoryBulkOperationValuePayload;
};

export type InventoryBulkOperationSummary = {
  selected_count: number;
  affected_count: number;
  unchanged_count: number;
  invalid_count: number;
  excluded_count: number;
  reversed_count: number;
  conflict_count: number;
};

export type InventoryBulkOperationItem = {
  id: string;
  inventory_item_id: string;
  inventory_item_name: string | null;
  inventory_item_internal_code: string | null;
  field_name: string;
  old_value_json: Record<string, unknown> | null;
  new_value_json: Record<string, unknown> | null;
  product_updated_at_snapshot: string;
  status: InventoryBulkOperationItemStatus;
  error_message: string | null;
  reverted_at: string | null;
  created_at: string;
};

export type InventoryBulkOperation = {
  id: string;
  operation_type: InventoryBulkOperationType;
  selection_mode: InventoryBulkSelectionMode;
  filters_json: Record<string, unknown> | null;
  request_json: Record<string, unknown>;
  status: InventoryBulkOperationStatus;
  selected_count: number;
  affected_count: number;
  unchanged_count: number;
  invalid_count: number;
  excluded_count: number;
  reversed_count: number;
  conflict_count: number;
  expires_at: string;
  confirmed_at: string | null;
  reversed_at: string | null;
  reversed_by_user_id: string | null;
  reversed_by_user_name?: string | null;
  reversed_by_user_email?: string | null;
  reversal_reason: string | null;
  created_by_user_id?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  created_at: string;
  items: InventoryBulkOperationItem[];
  summary: InventoryBulkOperationSummary | null;
};

export type InventoryBulkOperationListItem = Omit<
  InventoryBulkOperation,
  "filters_json" | "request_json" | "expires_at" | "reversed_by_user_id" | "reversal_reason" | "created_by_user_id" | "items" | "summary"
>;

export type InventoryImportMode = "initial_load" | "catalog_update";
export type InventoryImportStatus = "preview" | "confirmed" | "failed" | "expired";
export type InventoryImportRowStatus = "valid" | "warning" | "error" | "skipped";
export type InventoryImportRowAction = "create" | "update" | "skip" | "review_required";
export type InventoryImportMatchType =
  | "exact_match"
  | "possible_match"
  | "new_product"
  | "duplicate_in_file"
  | "conflict"
  | "invalid";

export type InventoryImportSummary = {
  row_count: number;
  valid_count: number;
  warning_count: number;
  error_count: number;
  create_count: number;
  update_count: number;
  skip_count: number;
  movement_count: number;
  stock_increase_total: string;
  stock_decrease_total: string;
  warnings: string[];
};

export type InventoryImportRow = {
  id: string;
  row_number: number;
  normalized_data: Record<string, string | number | boolean | null>;
  existing_inventory_item_id: string | null;
  match_type: InventoryImportMatchType;
  proposed_action: InventoryImportRowAction;
  status: InventoryImportRowStatus;
  errors: string[];
  warnings: string[];
  product_snapshot: Record<string, string | number | boolean | null> | null;
  changed_fields: string[];
  stock_current: string | null;
  stock_target: string | null;
  stock_delta: string | null;
  expected_movement_type: InventoryMovementType | null;
};

export type InventoryImport = {
  id: string;
  mode: InventoryImportMode;
  status: InventoryImportStatus;
  original_filename: string;
  file_hash: string;
  row_count: number;
  valid_count: number;
  warning_count: number;
  error_count: number;
  operation_id: string | null;
  result_summary: Record<string, unknown> | null;
  expires_at: string;
  confirmed_at: string | null;
  created_by_user_id?: string | null;
  created_by_user_name?: string | null;
  created_by_user_email?: string | null;
  created_at: string;
  rows: InventoryImportRow[];
  summary: InventoryImportSummary | null;
};

export type InventoryImportListItem = Omit<
  InventoryImport,
  "file_hash" | "result_summary" | "created_by_user_id" | "rows" | "summary"
>;

export type InventoryImportConfirmRow = {
  row_id: string;
  selected: boolean;
  action: InventoryImportRowAction;
};

export type InventoryImportConfirmPayload = {
  explicit_confirm: boolean;
  rows: InventoryImportConfirmRow[];
  reason?: string | null;
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
  attending_user_id?: string;
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

export type AppRole = "superadmin" | "medico_veterinario" | "contador";

export type CurrentUser = {
  id: string;
  email: string;
  full_name: string;
  role: AppRole;
  is_active: boolean;
  tenant_id: string;
  tenant_name: string;
};

export type AdminUser = {
  id: string;
  full_name: string;
  email: string;
  role: AppRole;
  is_active: boolean;
  tenant_id: string;
  tenant_name: string;
  created_at: string;
  updated_at: string;
};

export type TenantOption = {
  id: string;
  name: string;
};

export type InviteUserPayload = {
  email: string;
  full_name: string;
  role: AppRole;
  tenant_id: string;
};

export type InviteUserResult = {
  user: AdminUser;
  password_reset_link: string | null;
};

export type ListUsersFilters = {
  tenant_id?: string;
  is_active?: boolean;
  search?: string;
};

export type PurchaseStatus =
  | "draft"
  | "cancelled"
  | "received"
  | "partially_received"
  | "returned"
  | "reversed";

export type PurchaseDocumentType =
  | "invoice"
  | "receipt"
  | "ticket"
  | "delivery_note"
  | "other";

export type PurchaseAttachmentStatus = "pending" | "attached";
export type PurchaseReturnStatus = "draft" | "confirmed" | "cancelled";
export type PurchaseReturnAggregationStatus = "none" | "partial" | "full";
export type PurchaseReturnDocumentType = "credit_note" | "return_delivery_note" | "other";

export type PurchaseCreatorOption = {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
};

export type PurchaseAttachment = {
  id: string;
  original_filename: string;
  content_type: "application/pdf" | "image/jpeg" | "image/png";
  size_bytes: number;
  sha256: string;
  uploaded_by_user_id: string | null;
  uploaded_by_user_name: string | null;
  uploaded_by_user_email: string | null;
  uploaded_at: string;
  is_active: boolean;
  replaced_at: string | null;
  replaced_by_user_id: string | null;
  replaced_by_user_name: string | null;
  replaced_by_user_email: string | null;
  created_at: string;
  updated_at: string;
};

export type PurchaseItemInput = {
  inventory_item_id: string;
  quantity: string;
  unit_price_without_tax_ars: string;
  tax_rate_percentage: string;
};

export type PurchaseItem = PurchaseItemInput & {
  id: string;
  line_number: number;
  description_snapshot: string;
  internal_code_snapshot: string;
  unit: string;
  unit_price_with_tax_ars: string;
  line_subtotal_ars: string;
  line_tax_ars: string;
  line_total_ars: string;
  previous_purchase_price_ars: string | null;
  previous_purchase_tax_rate_percentage: string | null;
  confirmed_returned_quantity: string;
  returnable_quantity: string;
  created_at: string;
  updated_at: string;
};

export type SupplierSummary = {
  id: string;
  name: string;
  tax_id: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  updated_at: string;
};

export type Supplier = SupplierSummary & {
  tenant_id: string;
  address: string | null;
  notes: string | null;
  created_by_user_id: string | null;
  created_by_user_name: string | null;
  created_by_user_email: string | null;
  created_at: string;
};

export type SupplierWritePayload = {
  name: string;
  tax_id?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
};

export type SupplierListFilters = {
  search?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: "name" | "updated_at";
  sort_direction?: "asc" | "desc";
};

export type PurchaseSummary = {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_tax_id: string | null;
  purchase_date: string;
  document_type: PurchaseDocumentType;
  document_number: string | null;
  currency: "ARS";
  subtotal_ars: string;
  tax_total_ars: string;
  total_ars: string;
  status: PurchaseStatus;
  item_count: number;
  attachment_status: PurchaseAttachmentStatus;
  return_status: PurchaseReturnAggregationStatus;
  created_by_user_id: string | null;
  created_by_user_name: string | null;
  created_by_user_email: string | null;
  created_at: string;
  updated_at: string;
};

export type Purchase = Omit<PurchaseSummary, "item_count"> & {
  tenant_id: string;
  supplier: SupplierSummary | null;
  notes: string | null;
  cancelled_at: string | null;
  cancelled_by_user_id: string | null;
  cancelled_by_user_name: string | null;
  cancelled_by_user_email: string | null;
  cancellation_reason: string | null;
  received_at: string | null;
  received_by_user_id: string | null;
  received_by_user_name: string | null;
  received_by_user_email: string | null;
  inventory_operation_id: string | null;
  reversed_at: string | null;
  reversed_by_user_id: string | null;
  reversed_by_user_name: string | null;
  reversed_by_user_email: string | null;
  reversal_reason: string | null;
  reversal_operation_id: string | null;
  reversal_warnings: string[];
  attachment: PurchaseAttachment | null;
  attachment_history: PurchaseAttachment[];
  returned_total_ars: string;
  confirmed_return_count: number;
  can_register_return: boolean;
  returns: PurchaseReturnSummary[];
  items: PurchaseItem[];
};

export type PurchaseReturnItemInput = { purchase_item_id: string; quantity: string };

export type PurchaseReturnItem = PurchaseReturnItemInput & {
  id: string;
  inventory_item_id: string;
  line_number: number;
  description_snapshot: string;
  internal_code_snapshot: string;
  unit: string;
  unit_price_without_tax_ars: string;
  tax_rate_percentage: string;
  line_subtotal_ars: string;
  line_tax_ars: string;
  line_total_ars: string;
  created_at: string;
  updated_at: string;
};

export type PurchaseReturnSummary = {
  id: string;
  purchase_id: string;
  supplier_id: string;
  supplier_name: string;
  return_date: string;
  status: PurchaseReturnStatus;
  reason: string;
  document_type: PurchaseReturnDocumentType | null;
  document_number: string | null;
  subtotal_ars: string;
  tax_total_ars: string;
  total_ars: string;
  item_count: number;
  attachment_status: PurchaseAttachmentStatus;
  created_by_user_id: string | null;
  created_by_user_name: string | null;
  created_by_user_email: string | null;
  created_at: string;
  updated_at: string;
};

export type PurchaseReturn = Omit<PurchaseReturnSummary, "item_count"> & {
  tenant_id: string;
  supplier_tax_id: string | null;
  currency: "ARS";
  inventory_operation_id: string | null;
  confirmed_at: string | null;
  confirmed_by_user_id: string | null;
  confirmed_by_user_name: string | null;
  confirmed_by_user_email: string | null;
  cancelled_at: string | null;
  cancelled_by_user_id: string | null;
  cancelled_by_user_name: string | null;
  cancelled_by_user_email: string | null;
  cancellation_reason: string | null;
  attachment: PurchaseAttachment | null;
  attachment_history: PurchaseAttachment[];
  purchase: {
    id: string;
    purchase_date: string;
    supplier_id: string;
    supplier_name: string;
    document_type: PurchaseDocumentType;
    document_number: string | null;
    total_ars: string;
    status: PurchaseStatus;
  };
  items: PurchaseReturnItem[];
};

export type PurchaseReturnWritePayload = {
  return_date: string;
  reason: string;
  document_type?: PurchaseReturnDocumentType | null;
  document_number?: string | null;
  items: PurchaseReturnItemInput[];
};

export type PurchaseWritePayload = {
  supplier_id: string;
  purchase_date: string;
  document_type: PurchaseDocumentType;
  document_number?: string | null;
  notes?: string | null;
  items: PurchaseItemInput[];
};

export type PurchaseListFilters = {
  search?: string;
  supplier?: string;
  supplier_id?: string;
  status?: "draft" | "cancelled" | "received" | "reversed";
  document_type?: PurchaseDocumentType;
  date_from?: string;
  date_to?: string;
  created_by_user_id?: string;
  attachment_status?: PurchaseAttachmentStatus;
  page?: number;
  page_size?: number;
  sort_by?: "purchase_date" | "created_at" | "total_ars" | "supplier_name" | "status";
  sort_direction?: "asc" | "desc";
};

export type PurchaseListSummary = {
  purchase_count: number;
  subtotal_ars: string;
  tax_total_ars: string;
  total_ars: string;
};

export type PurchaseDashboardFilters = {
  date_from?: string;
  date_to?: string;
  supplier_id?: string;
  created_by_user_id?: string;
  document_type?: PurchaseDocumentType;
};

export type PurchaseDashboardAttention = {
  id: string;
  purchase_date: string;
  supplier_name: string;
  document_number: string | null;
  total_ars: string;
  status: PurchaseStatus;
  attachment_status: PurchaseAttachmentStatus;
  alerts: Array<"old_draft" | "attachment_pending" | "reversed_receipt" | "document_number_missing">;
  priority: "high" | "medium" | "info";
};

export type PurchaseDashboardTopSupplier = {
  supplier_id: string;
  supplier_name: string;
  purchase_count: number;
  registered_total_ars: string;
  received_total_ars: string;
};

export type PurchaseDashboardRecentPurchase = {
  id: string;
  purchase_date: string;
  supplier_name: string;
  document_type: PurchaseDocumentType;
  document_number: string | null;
  total_ars: string;
  status: PurchaseStatus;
  attachment_status: PurchaseAttachmentStatus;
  created_by_user_id: string | null;
  created_by_user_name: string | null;
  created_by_user_email: string | null;
  created_at: string;
};

export type PurchaseDashboard = {
  generated_at: string;
  period: { date_from: string; date_to: string };
  filters: {
    supplier_id: string | null;
    created_by_user_id: string | null;
    document_type: PurchaseDocumentType | null;
  };
  summary: {
    registered_total_ars: string;
    received_total_ars: string;
    returned_total_ars: string;
    net_received_total_ars: string;
    confirmed_return_count: number;
    registered_tax_total_ars: string;
    received_tax_total_ars: string;
    purchase_count: number;
    draft_count: number;
    received_count: number;
    reversed_count: number;
    cancelled_count: number;
    attachment_pending_count: number;
    attachment_attached_count: number;
  };
  attention: PurchaseDashboardAttention[];
  top_suppliers: PurchaseDashboardTopSupplier[];
  recent_purchases: PurchaseDashboardRecentPurchase[];
};

export type SaleStatus = "draft" | "confirmed" | "cancelled" | "reversed";
export type SaleLineType = "product" | "service";
export type FiscalDocumentType = "receipt_c" | "invoice_c";
export type SaleFiscalStatus = "pending" | "documented" | "requires_attention";
export type PaymentMethodType = "cash" | "bank_transfer" | "debit_card" | "credit_card" | "digital_wallet" | "other";
export type SalePaymentStatus = "unpaid" | "partial" | "paid" | "requires_attention";

export type PaymentMethod = {
  id: string;
  label: string;
  type: PaymentMethodType;
  is_active: boolean;
  sort_order: number;
  has_payments: boolean;
  created_at: string;
  updated_at: string;
};

export type PaymentMethodWritePayload = Pick<PaymentMethod, "label" | "type" | "is_active" | "sort_order">;

export type SalePayment = {
  id: string;
  sale_id: string;
  payment_method_id: string;
  payment_method_label_snapshot: string;
  payment_method_type_snapshot: PaymentMethodType;
  amount_ars: string;
  received_at: string;
  reference: string | null;
  notes: string | null;
  created_by_user_id: string | null;
  created_by_user_name: string | null;
  created_by_user_email: string | null;
  is_active: boolean;
  voided_at: string | null;
  voided_by_user_id: string | null;
  voided_by_user_name: string | null;
  voided_by_user_email: string | null;
  void_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type FiscalIssuer = {
  id: string;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  display_name: string;
  tax_id: string;
  is_active: boolean;
  can_issue_service_receipt_c: boolean;
  can_issue_product_invoice_c: boolean;
  service_document_type: FiscalDocumentType | null;
  service_document_code: string | null;
  product_document_type: FiscalDocumentType | null;
  product_document_code: string | null;
  created_at: string;
  updated_at: string;
};

export type FiscalIssuerWritePayload = Omit<
  FiscalIssuer,
  "id" | "user_name" | "user_email" | "created_at" | "updated_at"
>;

export type SaleFiscalDocumentFileVersion = {
  id: string;
  original_filename: string;
  content_type: "application/pdf" | "image/jpeg" | "image/png";
  size_bytes: number;
  sha256: string;
  uploaded_by_user_id: string | null;
  uploaded_at: string;
  replaced_at: string;
  replaced_by_user_id: string | null;
  replaced_by_user_name: string | null;
  replaced_by_user_email: string | null;
};

export type SaleFiscalDocument = {
  id: string;
  fiscal_issuer_id: string;
  issuer_user_id_snapshot: string;
  issuer_name_snapshot: string;
  issuer_tax_id_snapshot: string;
  document_type: FiscalDocumentType;
  document_code: string;
  document_number: string;
  issue_date: string;
  total_ars_snapshot: string;
  original_filename: string;
  content_type: "application/pdf" | "image/jpeg" | "image/png";
  size_bytes: number;
  sha256: string;
  uploaded_by_user_id: string | null;
  uploaded_by_user_name: string | null;
  uploaded_by_user_email: string | null;
  uploaded_at: string;
  is_active: boolean;
  file_history: SaleFiscalDocumentFileVersion[];
  created_at: string;
  updated_at: string;
};

export type SaleProductItemInput = {
  line_type: "product";
  inventory_item_id: string;
  quantity: string;
  unit_price_ars?: string | null;
  discount_percentage: string;
};

export type SaleServiceItemInput = {
  line_type: "service";
  description: string;
  quantity: string;
  unit_price_ars: string;
  discount_percentage: string;
};

export type SaleItemInput = SaleProductItemInput | SaleServiceItemInput;

export type SaleItem = {
  id: string;
  line_type: SaleLineType;
  inventory_item_id: string | null;
  service_id: string | null;
  description_snapshot: string;
  internal_code_snapshot: string | null;
  unit_snapshot: string;
  quantity: string;
  unit_price_ars: string;
  discount_percentage: string;
  line_subtotal_ars: string;
  line_discount_ars: string;
  line_total_ars: string;
  line_order: number;
  created_at: string;
  updated_at: string;
};

export type SaleSummary = {
  id: string;
  owner_id: string | null;
  patient_id: string | null;
  owner_name_snapshot: string | null;
  patient_name_snapshot: string | null;
  sale_date: string;
  currency: "ARS";
  subtotal_ars: string;
  discount_total_ars: string;
  total_ars: string;
  status: SaleStatus;
  fiscal_status: SaleFiscalStatus | null;
  paid_total_ars: string;
  balance_due_ars: string;
  payment_status: SalePaymentStatus | null;
  payment_requires_attention: boolean;
  item_count: number;
  created_by_user_id: string | null;
  created_by_user_name: string | null;
  created_by_user_email: string | null;
  created_at: string;
  updated_at: string;
};

export type Sale = Omit<SaleSummary, "item_count"> & {
  tenant_id: string;
  owner_document_snapshot: string | null;
  owner_email_snapshot: string | null;
  patient_species_snapshot: string | null;
  notes: string | null;
  cancelled_at: string | null;
  cancelled_by_user_id: string | null;
  cancelled_by_user_name: string | null;
  cancelled_by_user_email: string | null;
  cancellation_reason: string | null;
  confirmed_at: string | null;
  confirmed_by_user_id: string | null;
  confirmed_by_user_name: string | null;
  confirmed_by_user_email: string | null;
  inventory_operation_id: string | null;
  reversed_at: string | null;
  reversed_by_user_id: string | null;
  reversed_by_user_name: string | null;
  reversed_by_user_email: string | null;
  reversal_reason: string | null;
  reversal_operation_id: string | null;
  fiscal_document: SaleFiscalDocument | null;
  payments: SalePayment[];
  items: SaleItem[];
};

export type SaleWritePayload = {
  owner_id: string | null;
  patient_id: string | null;
  sale_date: string;
  notes?: string | null;
  items: SaleItemInput[];
};

export type SaleListFilters = {
  search?: string;
  owner_id?: string;
  patient_id?: string;
  status?: SaleStatus;
  line_type?: SaleLineType;
  date_from?: string;
  date_to?: string;
  created_by_user_id?: string;
  fiscal_status?: SaleFiscalStatus;
  payment_status?: SalePaymentStatus;
  page?: number;
  page_size?: number;
  sort_by?: "sale_date" | "created_at" | "total_ars" | "status";
  sort_direction?: "asc" | "desc";
};
