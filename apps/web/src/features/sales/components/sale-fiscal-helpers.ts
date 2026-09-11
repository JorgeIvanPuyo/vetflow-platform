import type { FiscalDocumentType, FiscalIssuer, Sale } from "@/types/api";

export function getIssuerDocumentPair(sale: Sale, issuer: FiscalIssuer): [FiscalDocumentType, string] | null {
  // Backend supplies the fiscal classification, including inventory medications.
  // Capability and mixed-sale checks mirror SaleFiscalDocumentService._validate_eligibility.
  const products = sale.items.some((item) => item.fiscal_line_type === "product");
  const services = sale.items.some((item) => item.fiscal_line_type === "service");
  if (products && services) {
    if (!issuer.can_issue_product_invoice_c || !issuer.can_issue_service_receipt_c) return null;
    if (issuer.product_document_type !== issuer.service_document_type || issuer.product_document_code !== issuer.service_document_code) return null;
    return issuer.product_document_type && issuer.product_document_code ? [issuer.product_document_type, issuer.product_document_code] : null;
  }
  if (products) return issuer.can_issue_product_invoice_c && issuer.product_document_type && issuer.product_document_code ? [issuer.product_document_type, issuer.product_document_code] : null;
  return services && issuer.can_issue_service_receipt_c && issuer.service_document_type && issuer.service_document_code ? [issuer.service_document_type, issuer.service_document_code] : null;
}
