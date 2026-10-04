import { api } from "@/lib/api";
import type { PaymentReport } from "@/types/api";

export type PaymentReportFilters = { date_from?: string; date_to?: string; payment_method_id?: string; page?: number; page_size?: number };
export type PaymentReportResponse = { data: PaymentReport; meta: { page: number; page_size: number; total: number; total_pages: number } };

export function getPaymentReport(filters: PaymentReportFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  return api.get<PaymentReportResponse>(`/api/v1/reports/payments${params.size ? `?${params}` : ""}`);
}
