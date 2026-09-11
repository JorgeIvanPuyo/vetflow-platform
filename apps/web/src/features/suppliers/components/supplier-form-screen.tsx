"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { createSupplier, getSupplier, updateSupplier } from "@/services/suppliers";
import type { SupplierWritePayload } from "@/types/api";


type Props = { supplierId?: string };

export function SupplierFormScreen({ supplierId }: Props) {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", taxId: "", phone: "", email: "", address: "", notes: "" });
  const [isActive, setIsActive] = useState(true);
  const [isLoading, setIsLoading] = useState(Boolean(supplierId));
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!supplierId) return;
    let active = true;
    getSupplier(supplierId)
      .then(({ data }) => {
        if (!active) return;
        setForm({ name: data.name, taxId: data.tax_id ?? "", phone: data.phone ?? "", email: data.email ?? "", address: data.address ?? "", notes: data.notes ?? "" });
        setIsActive(data.is_active);
      })
      .catch((error) => active && setErrorMessage(getApiErrorMessage(error)))
      .finally(() => active && setIsLoading(false));
    return () => { active = false; };
  }, [supplierId]);

  function setField(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) {
      setErrorMessage("Ingresa el nombre del proveedor.");
      return;
    }
    const payload: SupplierWritePayload = {
      name: form.name.trim(),
      tax_id: form.taxId.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      address: form.address.trim() || null,
      notes: form.notes.trim() || null,
    };
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const response = supplierId ? await updateSupplier(supplierId, { ...payload, is_active: isActive }) : await createSupplier(payload);
      router.push(`/suppliers/${response.data.id}`);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <div className="loading-card" aria-label="Cargando proveedor" />;

  return (
    <form className="page-stack suppliers-page" onSubmit={handleSubmit}>
      <section className="screen-heading list-page__header"><div><Link className="back-link" href={supplierId ? `/suppliers/${supplierId}` : "/suppliers"}><ArrowLeft size={18} /> {supplierId ? "Detalle" : "Proveedores"}</Link><h1>{supplierId ? "Editar proveedor" : "Nuevo proveedor"}</h1><p>El nombre y la identificación fiscal deben ser únicos dentro de la clínica.</p></div></section>
      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}
      <section className="panel supplier-form-grid">
        <label className="field"><span>Nombre *</span><input required maxLength={255} value={form.name} onChange={(event) => setField("name", event.target.value)} /></label>
        <label className="field"><span>Identificación fiscal</span><input maxLength={80} value={form.taxId} onChange={(event) => setField("taxId", event.target.value)} /></label>
        <label className="field"><span>Teléfono</span><input maxLength={50} value={form.phone} onChange={(event) => setField("phone", event.target.value)} /></label>
        <label className="field"><span>Email</span><input type="email" maxLength={255} value={form.email} onChange={(event) => setField("email", event.target.value)} /></label>
        {supplierId ? <label className="field"><span>Estado</span><select value={isActive ? "active" : "inactive"} onChange={(event) => setIsActive(event.target.value === "active")}><option value="active">Activo</option><option value="inactive">Inactivo</option></select></label> : null}
        <label className="field supplier-form-wide"><span>Dirección</span><textarea rows={3} maxLength={2000} value={form.address} onChange={(event) => setField("address", event.target.value)} /></label>
        <label className="field supplier-form-wide"><span>Notas</span><textarea rows={4} maxLength={4000} value={form.notes} onChange={(event) => setField("notes", event.target.value)} /></label>
      </section>
      <div className="supplier-form-actions">
        <Link className="secondary-button" href={supplierId ? `/suppliers/${supplierId}` : "/suppliers"}>Cancelar</Link>
        <button className="primary-button" type="submit" disabled={isSaving}>{isSaving ? "Guardando..." : "Guardar proveedor"}</button>
      </div>
    </form>
  );
}
