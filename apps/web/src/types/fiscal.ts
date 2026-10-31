import type { FiscalDocumentType, FiscalIssuer, PaymentMethod, PaymentMethodType, SaleFiscalDocument } from "./api";

export type FiscalPermissions = {
  can_manage_configuration: boolean;
  can_review_proposals: boolean;
  can_approve_proposals: boolean;
  own_issuer_only: boolean;
};

export type FiscalPolicy = {
  enabled: boolean;
  payment_scope: "electronic_only" | "all_payments";
  accounting_reviewed_at: string | null;
  accounting_reviewed_by_user_id: string | null;
  accounting_review_note: string | null;
  revision: number;
  production_blocked: boolean;
  external_emission_available: false;
  review_history: { policy_revision: number; payment_scope: FiscalPolicy["payment_scope"]; enabled: boolean; reviewed_at: string; reviewed_by_user_id: string; note: string }[];
};

export type FiscalPolicyInput = Pick<FiscalPolicy, "enabled" | "payment_scope"> & { accounting_review_note?: string };
export type FiscalSeriesInput = {
  fiscal_issuer_id: string;
  environment: "homologation" | "production";
  point_of_sale: number;
  document_type: FiscalDocumentType;
  concept: 1 | 2 | 3;
  authorization_mode: "CAE" | "CAEA";
  is_active: boolean;
  credential_reference: string | null;
  caea_reference: string | null;
};

export type FiscalSeries = FiscalSeriesInput & {
  id: string;
  cuit_snapshot: string | null;
  revision: number;
  readiness: "pending" | "ready";
  pending_reasons: string[];
  external_emission_available: false;
};

export type FiscalConfiguration = {
  policy: FiscalPolicy;
  issuers: FiscalIssuer[];
  series: FiscalSeries[];
  payment_methods: PaymentMethod[];
  permissions: FiscalPermissions;
};

export type FiscalPaymentClassification = "available" | "proposed" | "committed" | "excluded" | "pending";
export type FiscalReviewPayment = {
  payment_id: string;
  payment_method_id: string;
  amount_ars: string;
  label: string;
  type: PaymentMethodType;
  status: FiscalPaymentClassification;
  reason: string | null;
  suggested_fiscal_issuer_id: string | null;
  proposal_id?: string | null;
};

export type FiscalBlocker = { code: string; message: string };
export type FiscalProposal = {
  id: string;
  sale_id: string;
  fiscal_issuer_id: string;
  fiscal_series_id: string;
  status: "draft" | "approved" | "cancelled" | "sent" | "unknown" | "authorized" | "rejected" | "caea_pending";
  payment_ids: string[];
  fiscal_description: string;
  total_ars: string;
  currency: "ARS" | "USD";
  concept: 1 | 2 | 3;
  content_hash: string;
  source_snapshot_hash: string;
  snapshot: Record<string, unknown>;
  blockers: FiscalBlocker[];
  is_stale: boolean;
  created_at: string;
  approved_at: string | null;
  approved_by_user_id: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  allocations: { id: string; payment_id: string; amount_ars: string; is_active: boolean; reserved_at: string; released_at: string | null }[];
};

export type FiscalProposalInput = { payment_ids?: string[]; fiscal_series_id?: string; fiscal_description?: string };
export type FiscalReview = {
  policy: FiscalPolicy;
  eligibility: { eligible: boolean; blockers: FiscalBlocker[] };
  payments: FiscalReviewPayment[];
  proposals: FiscalProposal[];
  documents: SaleFiscalDocument[];
  totals: { active_payments_ars: string; committed_ars: string; proposed_ars: string; excluded_ars: string; pending_ars: string; available_ars: string };
  permissions: { can_generate: boolean; can_manage_configuration: boolean; can_approve: boolean; own_issuer_id: string | null };
  external_emission_available: false;
};
