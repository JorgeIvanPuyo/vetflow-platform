"use client";

import { ArrowLeft, FileUp, Plus, Search, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { formatPurchaseCurrency } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getInventoryItems } from "@/services/inventory";
import { createPurchase, getPurchase, updatePurchase, uploadPurchaseAttachment } from "@/services/purchases";
import { createSupplier, getSuppliers } from "@/services/suppliers";
import type { InventoryItem, PurchaseDocumentType, PurchaseItem, PurchaseWritePayload, SupplierSummary } from "@/types/api";


type EditableLine = {
  inventoryItemId: string;
  name: string;
  internalCode: string;
  unit: string;
  referenceCost: string | null;
  quantity: string;
  unitPrice: string;
  taxMode: "21" | "0" | "other";
  taxRate: string;
};

type Props = { purchaseId?: string };

export function PurchaseFormScreen({ purchaseId }: Props) {
  const router = useRouter();
  const isEditing = Boolean(purchaseId);
  const [selectedSupplier, setSelectedSupplier] = useState<SupplierSummary | null>(null);
  const [supplierQuery, setSupplierQuery] = useState("");
  const [supplierResults, setSupplierResults] = useState<SupplierSummary[]>([]);
  const [isSearchingSuppliers, setIsSearchingSuppliers] = useState(false);
  const [isSupplierOpen, setIsSupplierOpen] = useState(false);
  const [showQuickSupplier, setShowQuickSupplier] = useState(false);
  const [quickSupplier, setQuickSupplier] = useState({ name: "", taxId: "", phone: "", email: "" });
  const [isCreatingSupplier, setIsCreatingSupplier] = useState(false);
  const [quickSupplierErrorMessage, setQuickSupplierErrorMessage] = useState<string | null>(null);
  const [purchaseDate, setPurchaseDate] = useState(todayIso());
  const [documentType, setDocumentType] = useState<PurchaseDocumentType>("invoice");
  const [documentNumber, setDocumentNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null);
  const [existingAttachmentName, setExistingAttachmentName] = useState<string | null>(null);
  const [attachmentErrorMessage, setAttachmentErrorMessage] = useState<string | null>(null);
  const [lines, setLines] = useState<EditableLine[]>([]);
  const [productQuery, setProductQuery] = useState("");
  const [productResults, setProductResults] = useState<InventoryItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(isEditing);
  const [isSaving, setIsSaving] = useState(false);
  const [isCancelled, setIsCancelled] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const supplierRequestId = useRef(0);
  const supplierComboboxRef = useRef<HTMLDivElement>(null);
  const quickSupplierNameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!purchaseId) return;
    let active = true;
    getPurchase(purchaseId)
      .then(({ data }) => {
        if (!active) return;
        setSelectedSupplier(data.supplier);
        setSupplierQuery(data.supplier?.name ?? data.supplier_name);
        setPurchaseDate(data.purchase_date);
        setDocumentType(data.document_type);
        setDocumentNumber(data.document_number ?? "");
        setNotes(data.notes ?? "");
        setExistingAttachmentName(data.attachment?.original_filename ?? null);
        setLines(data.items.map(lineFromPurchaseItem));
        setIsCancelled(data.status !== "draft");
      })
      .catch((error) => active && setErrorMessage(getApiErrorMessage(error)))
      .finally(() => active && setIsLoading(false));
    return () => { active = false; };
  }, [purchaseId]);

  useEffect(() => {
    if (!isSupplierOpen || selectedSupplier) return;
    const timeout = window.setTimeout(async () => {
      const requestId = supplierRequestId.current + 1;
      supplierRequestId.current = requestId;
      setIsSearchingSuppliers(true);
      try {
        const response = await getSuppliers({
          search: supplierQuery.trim() || undefined,
          is_active: true,
          page: 1,
          page_size: 100,
          sort_by: "name",
          sort_direction: "asc",
        });
        if (supplierRequestId.current === requestId) setSupplierResults(response.data);
      } catch (error) {
        if (supplierRequestId.current === requestId) setErrorMessage(getApiErrorMessage(error));
      } finally {
        if (supplierRequestId.current === requestId) setIsSearchingSuppliers(false);
      }
    }, supplierQuery.trim() ? 180 : 0);
    return () => window.clearTimeout(timeout);
  }, [isSupplierOpen, selectedSupplier, supplierQuery]);

  useEffect(() => {
    if (!showQuickSupplier) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => quickSupplierNameRef.current?.focus());
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape" && !isCreatingSupplier) setShowQuickSupplier(false);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isCreatingSupplier, showQuickSupplier]);

  useEffect(() => {
    if (!isSupplierOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!supplierComboboxRef.current?.contains(event.target as Node)) setIsSupplierOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [isSupplierOpen]);

  const estimate = useMemo(() => lines.reduce(
    (totals, line) => {
      const quantity = positiveNumber(line.quantity);
      const price = nonNegativeNumber(line.unitPrice);
      const rate = nonNegativeNumber(line.taxRate);
      const subtotal = quantity * price;
      const tax = subtotal * rate / 100;
      return { subtotal: totals.subtotal + subtotal, tax: totals.tax + tax, total: totals.total + subtotal + tax };
    },
    { subtotal: 0, tax: 0, total: 0 },
  ), [lines]);

  async function handleQuickSupplier() {
    if (!quickSupplier.name.trim()) {
      setQuickSupplierErrorMessage("Ingresa el nombre del proveedor.");
      return;
    }
    setIsCreatingSupplier(true);
    setQuickSupplierErrorMessage(null);
    try {
      const response = await createSupplier({
        name: quickSupplier.name.trim(),
        tax_id: quickSupplier.taxId.trim() || null,
        phone: quickSupplier.phone.trim() || null,
        email: quickSupplier.email.trim() || null,
      });
      setSelectedSupplier(response.data);
      setSupplierResults([]);
      setSupplierQuery(response.data.name);
      setIsSupplierOpen(false);
      setQuickSupplier({ name: "", taxId: "", phone: "", email: "" });
      setShowQuickSupplier(false);
    } catch (error) {
      setQuickSupplierErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsCreatingSupplier(false);
    }
  }

  async function searchProducts() {
    setIsSearching(true);
    setErrorMessage(null);
    try {
      const response = await getInventoryItems({
        search: productQuery.trim() || undefined,
        is_active: true,
        page: 1,
        page_size: 12,
        sort_by: "name",
        sort_direction: "asc",
      });
      setProductResults(response.data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsSearching(false);
    }
  }

  function addProduct(item: InventoryItem) {
    if (lines.some((line) => line.inventoryItemId === item.id)) {
      setErrorMessage("Ese producto ya está agregado a la compra.");
      return;
    }
    setLines((current) => [...current, {
      inventoryItemId: item.id,
      name: item.name,
      internalCode: item.internal_code,
      unit: item.unit,
      referenceCost: item.purchase_price_ars,
      quantity: "1",
      unitPrice: item.purchase_price_ars ?? "0",
      taxMode: "21",
      taxRate: "21",
    }]);
    setErrorMessage(null);
  }

  function updateLine(index: number, updates: Partial<EditableLine>) {
    setLines((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, ...updates } : line));
  }

  function changeTaxMode(index: number, taxMode: EditableLine["taxMode"]) {
    updateLine(index, { taxMode, taxRate: taxMode === "other" ? "" : taxMode });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const validationMessage = validateForm({ supplierId: selectedSupplier?.id, purchaseDate, lines });
    if (validationMessage) {
      setErrorMessage(validationMessage);
      return;
    }
    if (attachmentFile) {
      const attachmentValidationMessage = await validateAttachmentFile(attachmentFile);
      if (attachmentValidationMessage) {
        setAttachmentErrorMessage(attachmentValidationMessage);
        return;
      }
    }
    const payload: PurchaseWritePayload = {
      supplier_id: selectedSupplier!.id,
      purchase_date: purchaseDate,
      document_type: documentType,
      document_number: documentNumber.trim() || null,
      notes: notes.trim() || null,
      items: lines.map((line) => ({
        inventory_item_id: line.inventoryItemId,
        quantity: line.quantity,
        unit_price_without_tax_ars: line.unitPrice,
        tax_rate_percentage: line.taxRate,
      })),
    };
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const response = purchaseId
        ? await updatePurchase(purchaseId, payload)
        : await createPurchase(payload);
      if (attachmentFile) {
        try {
          await uploadPurchaseAttachment(response.data.id, attachmentFile);
        } catch {
          router.push(`/purchases/${response.data.id}?attachment_upload=failed`);
          return;
        }
      }
      router.push(`/purchases/${response.data.id}`);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <div className="loading-card" aria-label="Cargando compra" />;

  if (isCancelled) {
    return (
      <div className="page-stack purchases-page">
        <section className="error-state">Esta compra ya no está en borrador y no puede editarse.</section>
        <Link className="secondary-button" href={`/purchases/${purchaseId}`}>Volver al detalle</Link>
      </div>
    );
  }

  return (
    <form className="page-stack purchases-page" onSubmit={handleSubmit}>
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href={purchaseId ? `/purchases/${purchaseId}` : "/purchases"}>
            <ArrowLeft size={18} /> {purchaseId ? "Detalle" : "Compras"}
          </Link>
          <h1>{isEditing ? "Editar compra" : "Nueva compra"}</h1>
          <p>El borrador no cambia stock ni genera movimientos de inventario.</p>
        </div>
      </section>

      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}

      <section className="panel purchase-form-section">
        <div className="section-heading"><h2>Cabecera</h2><p>Selecciona un proveedor del catálogo y completa el comprobante.</p></div>
        <div className="purchase-supplier-picker">
          <div className="purchase-supplier-combobox" ref={supplierComboboxRef}>
            <label className="field">
              <span>Proveedor *</span>
              <span className="purchase-supplier-combobox__control">
                <input
                  role="combobox"
                  aria-autocomplete="list"
                  aria-controls="purchase-supplier-options"
                  aria-expanded={isSupplierOpen}
                  value={supplierQuery}
                  onFocus={() => setIsSupplierOpen(true)}
                  onKeyDown={(event) => { if (event.key === "Escape") setIsSupplierOpen(false); }}
                  onChange={(event) => {
                    setSupplierQuery(event.target.value);
                    setSelectedSupplier(null);
                    setIsSupplierOpen(true);
                  }}
                  placeholder="Escribe para filtrar proveedores activos"
                />
                {selectedSupplier ? <button className="icon-button" type="button" aria-label="Cambiar proveedor" onClick={() => { setSelectedSupplier(null); setSupplierQuery(""); setIsSupplierOpen(true); }}><X size={17} /></button> : null}
              </span>
            </label>
            <button className="secondary-button" type="button" onClick={() => { setQuickSupplierErrorMessage(null); setShowQuickSupplier(true); }}><Plus size={17} /> Nuevo proveedor</button>
            {isSupplierOpen && !selectedSupplier ? (
              <div className="purchase-supplier-options" id="purchase-supplier-options" role="listbox" aria-label="Proveedores activos">
                {isSearchingSuppliers ? <p>Buscando proveedores...</p> : null}
                {!isSearchingSuppliers && supplierResults.length === 0 ? <p>No hay proveedores activos que coincidan.</p> : null}
                {supplierResults.map((supplier) => (
                  <button
                    key={supplier.id}
                    type="button"
                    role="option"
                    aria-selected="false"
                    onClick={() => {
                      setSelectedSupplier(supplier);
                      setSupplierQuery(supplier.name);
                      setSupplierResults([]);
                      setIsSupplierOpen(false);
                    }}
                  >
                    <span><strong>{supplier.name}</strong><small>{supplier.tax_id || "Sin identificación fiscal"}</small></span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          {selectedSupplier ? (
            <div className="purchase-selected-supplier">
              <span><small>Proveedor seleccionado</small><strong>{selectedSupplier.name}</strong><small>{selectedSupplier.tax_id || "Sin identificación fiscal"}{selectedSupplier.is_active ? "" : " · Inactivo (se conserva en esta compra)"}</small></span>
              <span className="badge supplier-status--active">Seleccionado</span>
            </div>
          ) : null}
        </div>
        <div className="purchase-header-grid">
          <label className="field"><span>Fecha *</span><input required type="date" value={purchaseDate} onChange={(event) => setPurchaseDate(event.target.value)} /></label>
          <label className="field"><span>Tipo de comprobante *</span><select value={documentType} onChange={(event) => setDocumentType(event.target.value as PurchaseDocumentType)}><option value="invoice">Factura</option><option value="receipt">Recibo</option><option value="ticket">Ticket</option><option value="delivery_note">Remito</option><option value="other">Otro</option></select></label>
          <label className="field"><span>Número</span><input maxLength={120} value={documentNumber} onChange={(event) => setDocumentNumber(event.target.value)} /></label>
          <label className="field purchase-notes-field"><span>Notas</span><textarea rows={3} maxLength={4000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
        </div>
      </section>

      <section className="panel purchase-form-section">
        <div className="section-heading"><h2>Productos</h2><p>Busca por nombre o código interno.</p></div>
        <div className="purchase-product-search">
          <label className="field"><span>Producto</span><input value={productQuery} onChange={(event) => setProductQuery(event.target.value)} placeholder="Nombre o código" /></label>
          <button className="secondary-button" type="button" disabled={isSearching} onClick={() => void searchProducts()}><Search size={17} /> {isSearching ? "Buscando..." : "Buscar"}</button>
        </div>
        {productResults.length > 0 ? (
          <div className="purchase-product-results" aria-label="Resultados de productos">
            {productResults.map((item) => (
              <button key={item.id} type="button" onClick={() => addProduct(item)} disabled={lines.some((line) => line.inventoryItemId === item.id)}>
                <span><strong>{item.name}</strong><small>{item.internal_code} · {item.unit}</small></span>
                <span><small>Costo actual</small><strong>{formatPurchaseCurrency(item.purchase_price_ars)}</strong></span>
                <Plus size={17} />
              </button>
            ))}
          </div>
        ) : null}

        {lines.length === 0 ? <p className="empty-state empty-state--compact">Agrega al menos un producto.</p> : (
          <div className="purchase-lines">
            {lines.map((line, index) => {
              const subtotal = positiveNumber(line.quantity) * nonNegativeNumber(line.unitPrice);
              const tax = subtotal * nonNegativeNumber(line.taxRate) / 100;
              const total = subtotal + tax;
              return (
                <article className="purchase-line" key={line.inventoryItemId}>
                  <div className="purchase-line__product"><strong>{line.name}</strong><small>{line.internalCode} · {line.unit}</small><small>Referencia: {formatPurchaseCurrency(line.referenceCost)}</small></div>
                  <div className="purchase-line__fields">
                    <label className="field"><span>Cantidad</span><input min="1" step="1" inputMode="numeric" type="number" value={line.quantity} onKeyDown={preventFractionalQuantityInput} onChange={(event) => updateLine(index, { quantity: event.target.value })} onBlur={() => { const value = Number(line.quantity); if (Number.isInteger(value) && value > 0) updateLine(index, { quantity: String(value) }); }} /></label>
                    <label className="field"><span>Costo sin IVA</span><input min="0" step="0.01" type="number" value={line.unitPrice} onChange={(event) => updateLine(index, { unitPrice: event.target.value })} /></label>
                    <label className="field"><span>IVA</span><select value={line.taxMode} onChange={(event) => changeTaxMode(index, event.target.value as EditableLine["taxMode"])}><option value="21">21%</option><option value="0">Sin IVA</option><option value="other">Otro porcentaje</option></select></label>
                  </div>
                  {line.taxMode === "other" ? <label className="field purchase-line__custom-tax"><span>IVA personalizado (%)</span><input min="0" max="100" step="0.01" type="number" value={line.taxRate} onChange={(event) => updateLine(index, { taxRate: event.target.value })} /></label> : null}
                  <div className="purchase-line__totals"><div><span>Subtotal</span><strong>{formatPurchaseCurrency(subtotal)}</strong></div><div><span>IVA</span><strong>{formatPurchaseCurrency(tax)}</strong></div><div><span>Total</span><strong>{formatPurchaseCurrency(total)}</strong></div></div>
                  <button className="secondary-button purchase-line__remove" type="button" aria-label={`Eliminar ${line.name}`} onClick={() => setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))}><Trash2 size={17} /> Eliminar línea</button>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="panel purchase-summary" aria-label="Resumen estimativo">
        <div><span>Subtotal</span><strong>{formatPurchaseCurrency(estimate.subtotal)}</strong></div>
        <div><span>IVA</span><strong>{formatPurchaseCurrency(estimate.tax)}</strong></div>
        <div><span>Total</span><strong>{formatPurchaseCurrency(estimate.total)}</strong></div>
        <p>Estimación visual. El backend recalcula y persiste los importes definitivos.</p>
      </section>

      <section className="panel purchase-form-section purchase-attachment-form">
        <div className="section-heading">
          <h2>Comprobante</h2>
          <p>Opcional. PDF, JPEG o PNG de hasta 10 MB. Se guarda de forma privada.</p>
        </div>
        {existingAttachmentName ? (
          <p className="purchase-attachment-current">
            Actual: <strong>{existingAttachmentName}</strong>. Al elegir otro archivo se conservará el anterior en el historial.
          </p>
        ) : null}
        <label className="purchase-attachment-picker">
          <FileUp size={22} />
          <span>{attachmentFile ? attachmentFile.name : existingAttachmentName ? "Reemplazar archivo" : "Seleccionar archivo"}</span>
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            onChange={(event) => {
              const selected = event.target.files?.[0] ?? null;
              setAttachmentFile(selected);
              setAttachmentErrorMessage(null);
              if (selected) {
                void validateAttachmentFile(selected).then(setAttachmentErrorMessage);
              }
            }}
          />
        </label>
        {attachmentFile ? <div className="purchase-attachment-selection"><small>{formatAttachmentSize(attachmentFile.size)} · se cargará después de guardar la compra</small><button className="secondary-button" type="button" onClick={() => { setAttachmentFile(null); setAttachmentErrorMessage(null); }}>Quitar selección</button></div> : null}
        <small>Puedes cargarlo ahora o agregarlo después desde el detalle de la compra.</small>
        {attachmentErrorMessage ? <div className="error-state" role="alert">{attachmentErrorMessage}</div> : null}
      </section>

      <div className="purchase-form-actions">
        <Link className="secondary-button" href={purchaseId ? `/purchases/${purchaseId}` : "/purchases"}>Cancelar</Link>
        <button className="primary-button" type="submit" disabled={isSaving}>{isSaving ? "Guardando..." : "Guardar borrador"}</button>
      </div>

      {showQuickSupplier ? createPortal(
        <div className="purchase-modal-backdrop" role="presentation">
          <section className="panel purchase-modal purchase-quick-supplier" role="dialog" aria-modal="true" aria-labelledby="quick-supplier-title">
            <button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar alta rápida" disabled={isCreatingSupplier} onClick={() => setShowQuickSupplier(false)}><X size={18} /></button>
            <div className="section-heading"><h2 id="quick-supplier-title">Nuevo proveedor</h2><p>Al guardarlo se seleccionará sin perder los datos ni las líneas de esta compra.</p></div>
            <div className="purchase-header-grid">
              <label className="field"><span>Nombre *</span><input ref={quickSupplierNameRef} maxLength={255} value={quickSupplier.name} onChange={(event) => setQuickSupplier((current) => ({ ...current, name: event.target.value }))} /></label>
              <label className="field"><span>Identificación fiscal</span><input maxLength={80} value={quickSupplier.taxId} onChange={(event) => setQuickSupplier((current) => ({ ...current, taxId: event.target.value }))} /></label>
              <label className="field"><span>Teléfono</span><input maxLength={50} value={quickSupplier.phone} onChange={(event) => setQuickSupplier((current) => ({ ...current, phone: event.target.value }))} /></label>
              <label className="field"><span>Email</span><input type="email" maxLength={255} value={quickSupplier.email} onChange={(event) => setQuickSupplier((current) => ({ ...current, email: event.target.value }))} /></label>
            </div>
            {quickSupplierErrorMessage ? <div className="error-state" role="alert">{quickSupplierErrorMessage}</div> : null}
            <div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isCreatingSupplier} onClick={() => setShowQuickSupplier(false)}>Cancelar</button><button className="primary-button" type="button" disabled={isCreatingSupplier} onClick={() => void handleQuickSupplier()}>{isCreatingSupplier ? "Guardando..." : "Crear y seleccionar"}</button></div>
          </section>
        </div>,
        document.body,
      ) : null}
    </form>
  );
}

function lineFromPurchaseItem(item: PurchaseItem): EditableLine {
  const taxRate = String(item.tax_rate_percentage);
  const normalizedRate = Number(taxRate);
  return {
    inventoryItemId: item.inventory_item_id,
    name: item.description_snapshot,
    internalCode: item.internal_code_snapshot,
    unit: item.unit,
    referenceCost: null,
    quantity: String(item.quantity),
    unitPrice: String(item.unit_price_without_tax_ars),
    taxMode: normalizedRate === 21 ? "21" : normalizedRate === 0 ? "0" : "other",
    taxRate,
  };
}

function validateForm({ supplierId, purchaseDate, lines }: { supplierId?: string; purchaseDate: string; lines: EditableLine[] }) {
  if (!supplierId) return "Selecciona un proveedor del catálogo.";
  if (!purchaseDate) return "Ingresa la fecha de compra.";
  if (lines.length === 0) return "Agrega al menos un producto.";
  for (const line of lines) {
    if (!Number.isInteger(Number(line.quantity)) || Number(line.quantity) <= 0) return "La cantidad debe ser un número entero mayor que cero.";
    if (!(Number(line.unitPrice) >= 0)) return `El precio de ${line.name} no puede ser negativo.`;
    const tax = Number(line.taxRate);
    if (!Number.isFinite(tax) || tax < 0 || tax > 100) return `El IVA de ${line.name} debe estar entre 0 y 100.`;
  }
  return null;
}

function preventFractionalQuantityInput(event: KeyboardEvent<HTMLInputElement>) {
  if ([".", ",", "e", "E", "+", "-"].includes(event.key)) event.preventDefault();
}

function positiveNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function nonNegativeNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function todayIso() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const ATTACHMENT_MIME_BY_EXTENSION: Record<string, string> = {
  pdf: "application/pdf",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
};

async function validateAttachmentFile(file: File) {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const expectedMime = ATTACHMENT_MIME_BY_EXTENSION[extension];
  if (!expectedMime) return "El comprobante debe ser PDF, JPEG o PNG.";
  if (file.type.toLowerCase() !== expectedMime) return "La extensión y el tipo del archivo no coinciden.";
  if (file.size === 0) return "El comprobante no puede estar vacío.";
  if (file.size > MAX_ATTACHMENT_BYTES) return "El comprobante supera el máximo de 10 MB.";
  const signature = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  const valid = expectedMime === "application/pdf"
    ? signature[0] === 0x25 && signature[1] === 0x50 && signature[2] === 0x44 && signature[3] === 0x46 && signature[4] === 0x2d
    : expectedMime === "image/jpeg"
      ? signature[0] === 0xff && signature[1] === 0xd8 && signature[2] === 0xff
      : signature.length >= 8 && [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((byte, index) => signature[index] === byte);
  return valid ? null : "El contenido del archivo no corresponde al formato seleccionado.";
}

function formatAttachmentSize(size: number) {
  return size >= 1024 * 1024
    ? `${(size / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(size / 1024))} KB`;
}
