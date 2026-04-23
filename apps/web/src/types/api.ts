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

export type CreateOwnerPayload = {
  full_name: string;
  phone: string;
  email?: string;
};

export type CreatePatientPayload = {
  owner_id: string;
  name: string;
  species: string;
  breed?: string;
  sex?: string;
  estimated_age?: string;
  weight_kg?: number;
};

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
