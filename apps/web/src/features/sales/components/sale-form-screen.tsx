"use client";

import { ArrowLeft, ChevronDown, PackagePlus, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import { useClinic } from "@/features/clinic/clinic-context";
import { formatPurchaseCurrency } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { resolveMoneyPreferences } from "@/lib/money";
import { getInventoryItems } from "@/services/inventory";
import { getOwners } from "@/services/owners";
import { getPatients } from "@/services/patients";
import { createSale, getSale, updateSale } from "@/services/sales";
import type { ClinicService, InventoryItem, Owner, Patient, SaleItem, SaleWritePayload } from "@/types/api";

import { SaleServiceSelector } from "./sale-service-selector";
import { hasValidServicePrice, serviceLineFromCatalog, serviceLineFromSnapshot, serviceLineToInput, type ServiceLine } from "./sale-service-helpers";

type ProductLine = { key: string; type: "product"; inventoryItemId: string; description: string; code: string; unit: string; stock: string; quantity: string; price: string; discount: string };

type Line = ProductLine | ServiceLine;

export function SaleFormScreen({ saleId }: { saleId?: string }) {
  const { preferences } = useClinic();
  const moneyPreferences = resolveMoneyPreferences(preferences);
  const router = useRouter();
  const [owners, setOwners] = useState<Owner[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [ownerId, setOwnerId] = useState("");
  const [patientId, setPatientId] = useState("");
  const [saleDate, setSaleDate] = useState(todayIso());
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [productQuery, setProductQuery] = useState("");
  const [products, setProducts] = useState<InventoryItem[]>([]);
  const [productPage, setProductPage] = useState(1);
  const [productTotalPages, setProductTotalPages] = useState(1);
  const [isProductSelectorOpen, setIsProductSelectorOpen] = useState(false);
  const [isSearchingProducts, setIsSearchingProducts] = useState(false);
  const [isLoadingMoreProducts, setIsLoadingMoreProducts] = useState(false);
  const [productSearchError, setProductSearchError] = useState<string | null>(null);
  const [productSearchRevision, setProductSearchRevision] = useState(0);
  const [activeProductIndex, setActiveProductIndex] = useState(-1);
  const [isLoading, setIsLoading] = useState(Boolean(saleId));
  const [isSaving, setIsSaving] = useState(false);
  const [isServiceSelectorOpen, setIsServiceSelectorOpen] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const productSelectorRef = useRef<HTMLDivElement>(null);
  const productInputRef = useRef<HTMLInputElement>(null);
  const productRequestIdRef = useRef(0);

  useEffect(() => {
    getOwners({ page: 1, pageSize: 100 }).then((response) => setOwners(response.data)).catch(() => setOwners([]));
  }, []);

  useEffect(() => {
    if (!ownerId) { setPatients([]); setPatientId(""); return; }
    getPatients({ ownerId, page: 1, pageSize: 100 }).then((response) => setPatients(response.data)).catch(() => setPatients([]));
  }, [ownerId]);

  useEffect(() => {
    if (!saleId) return;
    let active = true;
    getSale(saleId).then(({ data }) => {
      if (!active) return;
      if (data.status !== "draft") { setUnavailable(true); return; }
      setOwnerId(data.owner_id ?? ""); setPatientId(data.patient_id ?? ""); setSaleDate(data.sale_date); setNotes(data.notes ?? "");
      setLines(data.items.map(lineFromSaleItem));
    }).catch((error) => active && setErrorMessage(getApiErrorMessage(error))).finally(() => active && setIsLoading(false));
    return () => { active = false; };
  }, [saleId]);

  useEffect(() => {
    if (!isProductSelectorOpen) return;

    const requestId = ++productRequestIdRef.current;
    const search = productQuery.trim();
    setProducts([]);
    setProductPage(1);
    setProductTotalPages(1);
    setActiveProductIndex(-1);
    setProductSearchError(null);
    setIsSearchingProducts(true);

    const timeoutId = window.setTimeout(() => {
      getInventoryItems({
        search: search || undefined,
        is_active: true,
        page: 1,
        page_size: 30,
        sort_by: "name",
        sort_direction: "asc",
      }).then((response) => {
        if (productRequestIdRef.current !== requestId) return;
        setProducts(response.data);
        setProductPage(response.meta.page);
        setProductTotalPages(response.meta.total_pages);
      }).catch((error) => {
        if (productRequestIdRef.current !== requestId) return;
        setProductSearchError(getApiErrorMessage(error));
      }).finally(() => {
        if (productRequestIdRef.current === requestId) setIsSearchingProducts(false);
      });
    }, search ? 350 : 0);

    return () => window.clearTimeout(timeoutId);
  }, [isProductSelectorOpen, productQuery, productSearchRevision]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (productSelectorRef.current?.contains(event.target as Node)) return;
      productRequestIdRef.current += 1;
      setIsProductSelectorOpen(false);
      setActiveProductIndex(-1);
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  useEffect(() => {
    if (!isProductSelectorOpen || activeProductIndex < 0) return;
    document.getElementById(`sale-product-option-${products[activeProductIndex]?.id}`)?.scrollIntoView({ block: "nearest" });
  }, [activeProductIndex, isProductSelectorOpen, products]);

  const totals = useMemo(() => lines.reduce((sum, line) => {
    const subtotal = safeNumber(line.quantity) * safeNumber(line.price);
    const discount = subtotal * safeNumber(line.discount) / 100;
    return { subtotal: sum.subtotal + subtotal, discount: sum.discount + discount, total: sum.total + subtotal - discount };
  }, { subtotal: 0, discount: 0, total: 0 }), [lines]);

  const addedProductIds = useMemo(() => new Set(lines.flatMap((line) => line.type === "product" ? [line.inventoryItemId] : [])), [lines]);

  function closeProductSelector() {
    productRequestIdRef.current += 1;
    setIsProductSelectorOpen(false);
    setActiveProductIndex(-1);
    setIsSearchingProducts(false);
    setIsLoadingMoreProducts(false);
  }

  async function loadMoreProducts() {
    const nextPage = productPage + 1;
    const requestId = ++productRequestIdRef.current;
    setIsLoadingMoreProducts(true);
    setProductSearchError(null);
    try {
      const response = await getInventoryItems({
        search: productQuery.trim() || undefined,
        is_active: true,
        page: nextPage,
        page_size: 30,
        sort_by: "name",
        sort_direction: "asc",
      });
      if (productRequestIdRef.current !== requestId) return;
      setProducts((current) => {
        const knownIds = new Set(current.map((item) => item.id));
        return [...current, ...response.data.filter((item) => !knownIds.has(item.id))];
      });
      setProductPage(response.meta.page);
      setProductTotalPages(response.meta.total_pages);
    } catch (error) {
      if (productRequestIdRef.current === requestId) setProductSearchError(getApiErrorMessage(error));
    } finally {
      if (productRequestIdRef.current === requestId) setIsLoadingMoreProducts(false);
    }
  }

  function addProduct(item: InventoryItem) {
    if (lines.some((line) => line.type === "product" && line.inventoryItemId === item.id)) { setErrorMessage("Ese producto ya está agregado a la venta."); return; }
    setLines((current) => [...current, { key: item.id, type: "product", inventoryItemId: item.id, description: item.name, code: item.internal_code, unit: item.unit, stock: item.current_stock, quantity: "1", price: item.sale_price_ars ?? "0", discount: "0" }]);
    setProductQuery("");
    setProducts([]);
    setProductSearchError(null);
    closeProductSelector();
  }

  function handleProductKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    const selectableIndexes = products.flatMap((item, index) => addedProductIds.has(item.id) ? [] : [index]);

    if (event.key === "Escape" && isProductSelectorOpen) {
      event.preventDefault();
      closeProductSelector();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Enter") return;
    if (!isProductSelectorOpen) {
      event.preventDefault();
      setIsProductSelectorOpen(true);
      return;
    }
    if (!selectableIndexes.length) return;
    if (event.key === "Enter") {
      if (activeProductIndex >= 0) {
        event.preventDefault();
        addProduct(products[activeProductIndex]);
      }
      return;
    }

    event.preventDefault();
    const currentPosition = selectableIndexes.indexOf(activeProductIndex);
    const nextPosition = event.key === "ArrowDown"
      ? currentPosition < selectableIndexes.length - 1 ? currentPosition + 1 : 0
      : currentPosition > 0 ? currentPosition - 1 : selectableIndexes.length - 1;
    setActiveProductIndex(selectableIndexes[nextPosition]);
  }

  function addService(service: ClinicService) {
    setLines((current) => [...current, serviceLineFromCatalog(service, crypto.randomUUID())]);
    setIsServiceSelectorOpen(false);
  }

  function updateLine(key: string, changes: Partial<Line>) { setLines((current) => current.map((line) => line.key === key ? { ...line, ...changes } as Line : line)); }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const validation = validate(lines);
    if (validation) { setErrorMessage(validation); return; }
    const payload: SaleWritePayload = {
      owner_id: ownerId || null, patient_id: ownerId && patientId ? patientId : null, sale_date: saleDate, notes: notes.trim() || null,
      items: lines.map((line) => line.type === "product"
        ? { line_type: "product", inventory_item_id: line.inventoryItemId, quantity: line.quantity, unit_price_ars: line.price, discount_percentage: line.discount }
        : serviceLineToInput(line)),
    };
    setIsSaving(true); setErrorMessage(null);
    try { const response = saleId ? await updateSale(saleId, payload) : await createSale(payload); router.push(`/sales/${response.data.id}`); }
    catch (error) { setErrorMessage(getApiErrorMessage(error)); }
    finally { setIsSaving(false); }
  }

  if (isLoading) return <div className="loading-card" aria-label="Cargando venta" />;
  if (unavailable) return <div className="page-stack sales-page"><section className="error-state">Esta venta ya no está en borrador y no puede editarse.</section><Link className="secondary-button" href={`/sales/${saleId}`}>Volver al detalle</Link></div>;

  return <form className="page-stack sales-page" onSubmit={handleSubmit}>
    <section className="screen-heading list-page__header"><div><Link className="back-link" href={saleId ? `/sales/${saleId}` : "/sales"}><ArrowLeft size={18} /> {saleId ? "Detalle" : "Ventas"}</Link><h1>{saleId ? "Editar venta" : "Nueva venta"}</h1><p>El borrador no descuenta stock ni genera movimientos o comprobantes.</p></div></section>
    {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}
    <section className="panel sale-form-section"><div className="section-heading"><h2>Cliente y datos</h2><p>El cliente y paciente son opcionales para permitir ventas de mostrador.</p></div><div className="sale-header-grid">
      <label className="field"><span>Propietario</span><select value={ownerId} onChange={(event) => { setOwnerId(event.target.value); setPatientId(""); }}><option value="">Venta de mostrador</option>{owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.full_name}</option>)}</select></label>
      <label className="field"><span>Paciente</span><select disabled={!ownerId} value={patientId} onChange={(event) => setPatientId(event.target.value)}><option value="">{ownerId ? patients.length ? "Sin paciente" : "El propietario no tiene pacientes" : "Selecciona primero un propietario"}</option>{patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.name} · {patient.species}</option>)}</select></label>
      <label className="field"><span>Fecha *</span><input required type="date" value={saleDate} onChange={(event) => setSaleDate(event.target.value)} /></label>
      <label className="field sale-notes"><span>Notas</span><textarea rows={3} maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
    </div></section>
    <section className="panel sale-form-section"><div className="section-heading-inline"><div><h2>Líneas</h2><p>Agrega productos o servicios del catálogo de la clínica.</p></div><button className="secondary-button" type="button" disabled={isSaving} onClick={() => { closeProductSelector(); setIsServiceSelectorOpen(true); }}><Plus size={17} /> Agregar servicio</button></div>
      <div className="sale-product-selector" ref={productSelectorRef}>
        <label className="field" htmlFor="sale-product-search"><span>Producto</span></label>
        <div className="sale-product-selector__control">
          <Search aria-hidden="true" size={18} />
          <input
            id="sale-product-search"
            ref={productInputRef}
            role="combobox"
            aria-autocomplete="list"
            aria-controls="sale-product-options"
            aria-expanded={isProductSelectorOpen}
            aria-haspopup="listbox"
            aria-activedescendant={isProductSelectorOpen && activeProductIndex >= 0 ? `sale-product-option-${products[activeProductIndex]?.id}` : undefined}
            autoComplete="off"
            value={productQuery}
            placeholder="Explora productos o busca por nombre o código"
            onChange={(event) => { setProductQuery(event.target.value); setIsProductSelectorOpen(true); }}
            onClick={() => setIsProductSelectorOpen(true)}
            onFocus={() => setIsProductSelectorOpen(true)}
            onKeyDown={handleProductKeyDown}
          />
          <button
            type="button"
            aria-label={isProductSelectorOpen ? "Cerrar selector de productos" : "Abrir selector de productos"}
            onClick={() => {
              if (isProductSelectorOpen) closeProductSelector();
              else { setIsProductSelectorOpen(true); productInputRef.current?.focus(); }
            }}
          ><ChevronDown aria-hidden="true" size={18} /></button>
        </div>
        {isProductSelectorOpen ? <div className="sale-product-selector__dropdown">
          {isSearchingProducts ? <div className="sale-product-selector__state" role="status" aria-live="polite">Cargando productos...</div> : null}
          {!isSearchingProducts && productSearchError ? <div className="sale-product-selector__state sale-product-selector__state--error" role="alert"><span>No se pudieron cargar los productos. {productSearchError}</span><button className="secondary-button" type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => setProductSearchRevision((current) => current + 1)}>Reintentar</button></div> : null}
          {!isSearchingProducts && !productSearchError && !products.length ? <div className="sale-product-selector__state" role="status">{productQuery.trim() ? "No hay productos que coincidan con la búsqueda." : "No hay productos activos para mostrar."}</div> : null}
          <div id="sale-product-options" role="listbox" aria-label="Productos activos" aria-busy={isSearchingProducts || isLoadingMoreProducts}>
            {!isSearchingProducts && products.map((item, index) => {
              const isAdded = addedProductIds.has(item.id);
              return <button
                className="sale-product-selector__option"
                id={`sale-product-option-${item.id}`}
                type="button"
                role="option"
                aria-selected={activeProductIndex === index}
                disabled={isAdded}
                key={item.id}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => { if (!isAdded) setActiveProductIndex(index); }}
                onClick={() => addProduct(item)}
              ><span><strong>{item.name}</strong><small className="sale-product-selector__metadata"><span>{item.internal_code}</span><span>Stock {item.current_stock} {item.unit}</span></small></span><span className="sale-product-selector__price"><strong>{formatPurchaseCurrency(item.sale_price_ars ?? 0, moneyPreferences)}</strong>{isAdded ? <small>Ya agregado</small> : <PackagePlus aria-hidden="true" size={17} />}</span></button>;
            })}
          </div>
          {!isSearchingProducts && !productSearchError && productPage < productTotalPages ? <div className="sale-product-selector__footer"><button className="secondary-button" type="button" disabled={isLoadingMoreProducts} onMouseDown={(event) => event.preventDefault()} onClick={() => void loadMoreProducts()}>{isLoadingMoreProducts ? "Cargando..." : "Cargar más"}</button></div> : null}
        </div> : null}
      </div>
      <div className="sale-lines">{lines.map((line) => <article className="sale-line" key={line.key}><div className="sale-line__heading"><span>{line.type === "product" ? <><strong>{line.description}</strong><small>{line.code} · Stock actual {line.stock} {line.unit}</small></> : <label className="field"><span>Descripción del servicio *</span><input maxLength={255} value={line.description} onChange={(event) => updateLine(line.key, { description: event.target.value })} /></label>}</span><button className="icon-button" type="button" aria-label="Quitar línea" onClick={() => setLines((current) => current.filter((item) => item.key !== line.key))}><Trash2 size={17} /></button></div><div className="sale-line__fields">
        <label className="field"><span>Cantidad *</span><input required type="number" min="1" step="1" inputMode="numeric" value={line.quantity} onChange={(event) => updateLine(line.key, { quantity: event.target.value })} /></label>
        <label className="field"><span>Precio unitario *</span>{line.type === "service" && !line.price.trim() ? <small>Precio no configurado. Ingresa el precio para esta venta.</small> : null}<input required type="number" min="0" step="0.01" value={line.price} onChange={(event) => updateLine(line.key, { price: event.target.value })} /></label>
        <label className="field"><span>Descuento %</span><input required type="number" min="0" max="100" step="0.01" value={line.discount} onChange={(event) => updateLine(line.key, { discount: event.target.value })} /></label>
        <div className="sale-line__total"><span>Total estimado</span><strong>{formatPurchaseCurrency(lineTotal(line), moneyPreferences)}</strong></div>
      </div></article>)}</div>
      {!lines.length ? <p className="empty-state empty-state--compact">Agrega al menos un producto o servicio.</p> : null}
    </section>
    <section className="panel purchase-summary"><div><span>Subtotal</span><strong>{formatPurchaseCurrency(totals.subtotal, moneyPreferences)}</strong></div><div><span>Descuentos</span><strong>{formatPurchaseCurrency(totals.discount, moneyPreferences)}</strong></div><div><span>Total</span><strong>{formatPurchaseCurrency(totals.total, moneyPreferences)}</strong></div><p>Los importes definitivos se calculan en el backend.</p></section>
    <section className="purchase-form-actions"><Link className="secondary-button" href={saleId ? `/sales/${saleId}` : "/sales"}>Cancelar</Link><button className="primary-button" type="submit" disabled={isSaving}>{isSaving ? "Guardando..." : "Guardar borrador"}</button></section>
    {isServiceSelectorOpen ? <SaleServiceSelector moneyPreferences={moneyPreferences} onSelect={addService} onClose={() => setIsServiceSelectorOpen(false)} /> : null}
  </form>;
}

function safeNumber(value: string) { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0; }
function lineTotal(line: Line) { const subtotal = safeNumber(line.quantity) * safeNumber(line.price); return subtotal * (1 - safeNumber(line.discount) / 100); }
function todayIso() { const date = new Date(); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`; }
function validate(lines: Line[]) { if (!lines.length) return "Agrega al menos una línea."; for (const line of lines) { if (!Number.isInteger(Number(line.quantity)) || Number(line.quantity) <= 0) return "Todas las cantidades deben ser enteros positivos."; if (line.type === "service" && !line.description.trim()) return "Ingresa la descripción de cada servicio."; if (line.type === "service" && !hasValidServicePrice(line.price)) return "Ingresa un precio válido para cada servicio."; if (Number(line.price) < 0) return "El precio no puede ser negativo."; if (Number(line.discount) < 0 || Number(line.discount) > 100) return "El descuento debe estar entre 0 y 100."; } return null; }
function lineFromSaleItem(item: SaleItem): Line { return item.line_type === "product" ? { key: item.inventory_item_id!, type: "product", inventoryItemId: item.inventory_item_id!, description: item.description_snapshot, code: item.internal_code_snapshot ?? "Sin código", unit: item.unit_snapshot, stock: "Referencia no actualizada", quantity: item.quantity, price: item.unit_price_ars, discount: item.discount_percentage } : serviceLineFromSnapshot(item); }
