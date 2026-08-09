"use client";

import { ArrowLeft, FileUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { formatPurchaseCurrency, formatPurchaseDate } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { createPurchaseReturn, getPurchaseReturn, updatePurchaseReturn, uploadPurchaseReturnAttachment } from "@/services/purchase-returns";
import { getPurchase } from "@/services/purchases";
import type { Purchase, PurchaseReturnDocumentType, PurchaseReturnWritePayload } from "@/types/api";

type Props = { purchaseId?: string; returnId?: string };
type Quantities = Record<string, string>;

export function PurchaseReturnFormScreen({ purchaseId, returnId }: Props) {
  const router = useRouter();
  const isEditing = Boolean(returnId);
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [returnDate, setReturnDate] = useState(todayIso());
  const [reason, setReason] = useState("");
  const [documentType, setDocumentType] = useState<PurchaseReturnDocumentType | "">("");
  const [documentNumber, setDocumentNumber] = useState("");
  const [quantities, setQuantities] = useState<Quantities>({});
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [unavailableMessage, setUnavailableMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        if (returnId) {
          const returnResponse = await getPurchaseReturn(returnId);
          const current = returnResponse.data;
          if (current.status !== "draft") {
            if (active) setUnavailableMessage("Esta devolución ya no está en borrador y no puede editarse.");
            return;
          }
          const purchaseResponse = await getPurchase(current.purchase_id);
          if (!active) return;
          setPurchase(purchaseResponse.data);
          setReturnDate(current.return_date);
          setReason(current.reason);
          setDocumentType(current.document_type ?? "");
          setDocumentNumber(current.document_number ?? "");
          setQuantities(Object.fromEntries(current.items.map((item) => [item.purchase_item_id, item.quantity])));
        } else if (purchaseId) {
          const response = await getPurchase(purchaseId);
          if (!active) return;
          setPurchase(response.data);
          if (response.data.status !== "received" || !response.data.can_register_return) {
            setUnavailableMessage("Esta compra no tiene cantidades disponibles para devolución.");
          }
        }
      } catch (error) {
        if (active) setErrorMessage(getApiErrorMessage(error));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [purchaseId, returnId]);

  const estimate = useMemo(() => {
    if (!purchase) return { subtotal: 0, tax: 0, total: 0 };
    return purchase.items.reduce((total, item) => {
      const quantity = Number(quantities[item.id] || 0);
      const subtotal = quantity * Number(item.unit_price_without_tax_ars);
      const tax = subtotal * Number(item.tax_rate_percentage) / 100;
      return { subtotal: total.subtotal + subtotal, tax: total.tax + tax, total: total.total + subtotal + tax };
    }, { subtotal: 0, tax: 0, total: 0 });
  }, [purchase, quantities]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!purchase) return;
    if (!reason.trim()) {
      setErrorMessage("Ingresa el motivo de la devolución.");
      return;
    }
    const selected = purchase.items.flatMap((item) => {
      const raw = quantities[item.id]?.trim();
      return raw && Number(raw) > 0 ? [{ purchase_item_id: item.id, quantity: raw }] : [];
    });
    if (selected.length === 0) {
      setErrorMessage("Indica al menos una cantidad a devolver.");
      return;
    }
    for (const item of purchase.items) {
      const raw = quantities[item.id]?.trim();
      if (!raw || Number(raw) === 0) continue;
      if (!/^\d+$/.test(raw) || Number(raw) < 1) {
        setErrorMessage(`La cantidad de ${item.description_snapshot} debe ser un entero positivo.`);
        return;
      }
      if (Number(raw) > Number(item.returnable_quantity)) {
        setErrorMessage(`La cantidad de ${item.description_snapshot} supera lo disponible para devolución.`);
        return;
      }
    }
    if (attachmentFile) {
      const fileError = validateAttachment(attachmentFile);
      if (fileError) { setErrorMessage(fileError); return; }
    }
    const payload: PurchaseReturnWritePayload = {
      return_date: returnDate,
      reason: reason.trim(),
      document_type: documentType || null,
      document_number: documentNumber.trim() || null,
      items: selected,
    };
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const response = returnId
        ? await updatePurchaseReturn(returnId, payload)
        : await createPurchaseReturn(purchase.id, payload);
      if (attachmentFile) {
        try {
          await uploadPurchaseReturnAttachment(response.data.id, attachmentFile);
        } catch {
          router.push(`/purchase-returns/${response.data.id}?attachment_upload=failed`);
          return;
        }
      }
      router.push(`/purchase-returns/${response.data.id}`);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <div className="loading-card" aria-label="Cargando devolución" />;
  const backHref = returnId ? `/purchase-returns/${returnId}` : `/purchases/${purchaseId}`;
  if (unavailableMessage || (!purchase && errorMessage)) return <div className="page-stack purchases-page"><section className="error-state">{unavailableMessage ?? errorMessage}</section><Link className="secondary-button" href={backHref}>Volver</Link></div>;
  if (!purchase) return null;

  return (
    <form className="page-stack purchases-page" onSubmit={handleSubmit}>
      <section className="screen-heading list-page__header">
        <div><Link className="back-link" href={backHref}><ArrowLeft size={18} /> {isEditing ? "Devolución" : "Compra"}</Link><h1>{isEditing ? "Editar devolución" : "Registrar devolución"}</h1><p>Guarda un borrador sin modificar el stock.</p></div>
      </section>
      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}

      <section className="panel purchase-detail-grid">
        <div><span>Proveedor</span><strong>{purchase.supplier_name}</strong><small>{purchase.supplier_tax_id || "Sin identificación fiscal"}</small></div>
        <div><span>Compra original</span><strong>{formatPurchaseDate(purchase.purchase_date)}</strong><small>{purchase.document_number || "Sin número"}</small></div>
        <div><span>Total original</span><strong>{formatPurchaseCurrency(purchase.total_ars)}</strong><small>La compra permanece recibida</small></div>
      </section>

      <section className="panel purchase-form-section">
        <div className="section-heading"><h2>Datos de la devolución</h2><p>Los precios e IVA se toman de la compra original.</p></div>
        <div className="purchase-header-grid">
          <label className="field"><span>Fecha *</span><input required type="date" value={returnDate} onChange={(event) => setReturnDate(event.target.value)} /></label>
          <label className="field"><span>Tipo de documento</span><select value={documentType} onChange={(event) => setDocumentType(event.target.value as PurchaseReturnDocumentType | "")}><option value="">Sin especificar</option><option value="credit_note">Nota de crédito</option><option value="return_delivery_note">Remito de devolución</option><option value="other">Otro</option></select></label>
          <label className="field"><span>Número</span><input maxLength={120} value={documentNumber} onChange={(event) => setDocumentNumber(event.target.value)} /></label>
          <label className="field purchase-notes-field"><span>Motivo *</span><textarea required rows={4} maxLength={2000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        </div>
      </section>

      <section className="inventory-table-card" aria-label="Cantidades a devolver">
        <div className="inventory-table-scroll"><table className="inventory-table purchase-table"><thead><tr><th>Producto</th><th>Comprada</th><th>Ya devuelta</th><th>Disponible</th><th>A devolver</th><th>Total estimado</th></tr></thead><tbody>{purchase.items.map((item) => {
          const quantity = Number(quantities[item.id] || 0);
          const total = quantity * Number(item.unit_price_without_tax_ars) * (1 + Number(item.tax_rate_percentage) / 100);
          return <tr key={item.id} className="inventory-table__row--static"><td className="purchase-wrap"><strong>{item.description_snapshot}</strong><small>{item.internal_code_snapshot} · {item.unit}</small></td><td>{item.quantity}</td><td>{item.confirmed_returned_quantity}</td><td><strong>{item.returnable_quantity}</strong></td><td><input className="purchase-return-quantity" aria-label={`Cantidad a devolver de ${item.description_snapshot}`} type="number" inputMode="numeric" min="0" max={item.returnable_quantity} step="1" value={quantities[item.id] ?? ""} onChange={(event) => setQuantities((current) => ({ ...current, [item.id]: event.target.value }))} /></td><td>{formatPurchaseCurrency(total)}</td></tr>;
        })}</tbody></table></div>
      </section>

      <section className="panel purchase-summary"><div><span>Subtotal estimado</span><strong>{formatPurchaseCurrency(estimate.subtotal)}</strong></div><div><span>IVA estimado</span><strong>{formatPurchaseCurrency(estimate.tax)}</strong></div><div><span>Total estimado</span><strong>{formatPurchaseCurrency(estimate.total)}</strong></div><p>El backend recalculará y guardará los importes definitivos con los valores históricos.</p></section>

      {!isEditing ? <section className="panel purchase-form-section"><div className="section-heading"><h2>Comprobante opcional</h2><p>PDF, JPEG o PNG de hasta 10 MB. También podrás adjuntarlo después.</p></div><label className="purchase-attachment-picker"><FileUp size={22} /><span>{attachmentFile?.name ?? "Seleccionar archivo"}</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(event) => setAttachmentFile(event.target.files?.[0] ?? null)} /></label></section> : null}

      <section className="purchase-form-actions"><Link className="secondary-button" href={backHref}>Cancelar</Link><button className="primary-button" type="submit" disabled={isSaving}>{isSaving ? "Guardando..." : "Guardar borrador"}</button></section>
    </form>
  );
}

function todayIso() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function validateAttachment(file: File) {
  const allowed = ["application/pdf", "image/jpeg", "image/png"];
  if (!allowed.includes(file.type)) return "El comprobante debe ser PDF, JPEG o PNG.";
  if (file.size === 0) return "El comprobante no puede estar vacío.";
  if (file.size > 10 * 1024 * 1024) return "El comprobante supera el máximo de 10 MB.";
  return null;
}
