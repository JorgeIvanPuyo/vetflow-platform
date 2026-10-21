export type FiscalBusinessPayload = {
  environment: "homologation" | "production";
  issuer: { cuit: string; legal_name: string; tax_condition: string; fiscal_address: string; gross_income_registration: string | null; activity_start_date: string | null; fiscal_data_review_note: string | null };
  receiver: { document_type: number; document_number: number; iva_condition_id: number; name: string; address: string; consumer_final: boolean };
  point_of_sale: number;
  document_type: 11 | 15;
  concept: 1 | 2 | 3;
  voucher_date: string;
  service_from: string | null;
  service_to: string | null;
  payment_due: string | null;
  currency: "PES";
  exchange_rate: string;
  total: string;
  net_amount: string;
  lines: { description: string; quantity: string; unit_price: string; total: string }[];
  number?: number | null;
};

export type FiscalEmission = {
  id: string;
  proposal_id: string;
  sale_id: string;
  status: "prepared" | "processing" | "unknown" | "conflict" | "rejected" | "authorized";
  environment: "homologation" | "production";
  request_hash: string;
  business_snapshot: FiscalBusinessPayload;
  number: number | null;
  cae: string | null;
  cae_expiry: string | null;
  document_id: string | null;
  file_status: "pending" | "ready" | "failed";
  diagnostics: { code: string; message: string }[];
  next_action_at: string | null;
  created_at: string;
  updated_at: string;
  attempts: { action: string; outcome: string; created_at: string }[];
  file_versions: { id: string; sha256: string; created_at: string }[];
  allowed_actions: { issue: boolean; reconcile: boolean; regenerate: boolean; download: boolean; retry_same_request?: boolean };
};

export type FiscalEmissions = {
  operations: FiscalEmission[];
  permissions: { can_prepare: boolean; can_issue: boolean; can_reconcile: boolean; can_regenerate: boolean; own_issuer_id: string | null };
  external_validation: "pending" | "validated";
  production_blocked: true;
};

export type FiscalEmissionReadiness = {
  credential: { status: string; fingerprint?: string | null; expires_at?: string | null; diagnostic: string | null };
  remote_validation: "pending" | "validated";
  parameters: Record<string, unknown[]> | null;
  blockers: { code: string; message: string }[];
  production_blocked: true;
  allowed_actions?: { validate: boolean };
};
