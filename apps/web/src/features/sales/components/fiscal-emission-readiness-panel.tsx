"use client";

import { useRef, useState } from "react";
import { getApiErrorMessage } from "@/lib/api";
import { getFiscalEmissionReadiness, validateFiscalEmissionReadiness } from "@/services/arca-emission";
import type { FiscalConfiguration } from "@/types/fiscal";
import type { FiscalEmissionReadiness } from "@/types/arca-emission";

const PARAMETER_LABELS: Record<string, string> = {
  FEParamGetTiposCbte: "Tipos de comprobante", FEParamGetPtosVenta: "Puntos de venta", FEParamGetTiposDoc: "Documentos de receptor", FEParamGetTiposConcepto: "Conceptos", FEParamGetTiposMonedas: "Monedas", FEParamGetCondicionIvaReceptor: "Condiciones de IVA del receptor",
};

export function FiscalEmissionReadinessPanel({ configuration }: { configuration: FiscalConfiguration }) {
  const [seriesId, setSeriesId] = useState("");
  const [readiness, setReadiness] = useState<FiscalEmissionReadiness | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [remoteConfirmed, setRemoteConfirmed] = useState(false);
  const remoteInFlight = useRef(false);
  async function load() {
    if (!seriesId || busy) return;
    setBusy(true); setError(null); setReadiness(null); setRemoteConfirmed(false);
    try { setReadiness((await getFiscalEmissionReadiness(seriesId)).data); }
    catch (value) { setError(getApiErrorMessage(value)); }
    finally { setBusy(false); }
  }
  async function validateRemote() {
    if (!seriesId || !remoteConfirmed || readiness?.allowed_actions?.validate !== true || remoteInFlight.current) return;
    remoteInFlight.current = true; setBusy(true); setError(null); setRemoteConfirmed(false);
    try { setReadiness((await validateFiscalEmissionReadiness(seriesId)).data); }
    catch (value) { setError(getApiErrorMessage(value)); }
    finally { remoteInFlight.current = false; setBusy(false); }
  }
  const credentialLabel = readiness?.credential.status && ({ ready: "Material de credencial disponible", available: "Material de credencial disponible", configured: "Referencia configurada; material pendiente de validación", provisioned: "Credencial provisionada", missing: "Credencial pendiente de provisión", not_configured: "Proveedor sin configurar", not_provisioned: "Credencial pendiente de provisión", disabled: "Proveedor desactivado", expired: "Certificado vencido", invalid: "Requiere revisión de credencial" } as Record<string, string>)[readiness.credential.status];
  return <section className="panel fiscal-card" aria-label="Preparación de emisión electrónica"><h2>Preparación de credenciales y parámetros</h2><p>Una referencia opaca no acredita que exista un certificado. La provisión se realiza fuera de la aplicación, sin cargar claves ni certificados aquí.</p><p>Homologación externa pendiente de accesos y validación. Producción bloqueada; CAEA y los circuitos de corrección fiscal requieren su preparación específica.</p>
    <label className="field" htmlFor="readiness-series"><span>Serie a consultar</span><select id="readiness-series" value={seriesId} disabled={busy} onChange={(event) => { setSeriesId(event.target.value); setReadiness(null); setRemoteConfirmed(false); }}><option value="">Selecciona una serie</option>{configuration.series.map((series) => <option key={series.id} value={series.id}>{series.cuit_snapshot || "CUIT pendiente"} · {series.environment === "homologation" ? "Homologación" : "Producción"} · PV {series.point_of_sale} · {series.document_type === "invoice_c" ? "Factura C" : "Recibo C"}</option>)}</select></label>
    <button className="secondary-button" type="button" disabled={busy || !seriesId} onClick={() => void load()}>{busy ? "Consultando estado..." : "Consultar preparación de homologación"}</button><small>Esta consulta muestra metadatos locales y parámetros ya validados; no prueba una habilitación remota por sí sola.</small>
    {error ? <div className="error-state" role="alert">{error}</div> : null}
    {readiness ? <div className="fiscal-card"><strong>{credentialLabel || "Credencial pendiente de verificar"}</strong>{readiness.credential.diagnostic ? <p>{readiness.credential.diagnostic}</p> : null}{readiness.credential.fingerprint ? <small>Huella: {readiness.credential.fingerprint}</small> : null}{readiness.credential.expires_at ? <small>Vencimiento del ticket: {readiness.credential.expires_at}</small> : null}<strong>{readiness.remote_validation === "validated" ? "Parámetros remotos consultados; revisar habilitación efectiva del emisor" : "Validación remota pendiente"}</strong>
      {readiness.blockers.map((blocker) => <p key={blocker.code} role="status">{blocker.message}</p>)}
      <fieldset className="fiscal-fields" disabled={busy || readiness.allowed_actions?.validate !== true}><label className="checkbox-field"><input type="checkbox" checked={remoteConfirmed} onChange={(event) => setRemoteConfirmed(event.target.checked)} /><span>Confirmo consultar WSAA y parámetros de homologación para esta serie con sus credenciales provisionadas. Esta consulta no emite comprobantes.</span></label><button className="secondary-button" type="button" disabled={busy || !remoteConfirmed || readiness.allowed_actions?.validate !== true} onClick={() => void validateRemote()}>Validar acceso y parámetros remotos de homologación</button></fieldset>
      {readiness.allowed_actions?.validate !== true ? <small>La validación remota requiere permiso fiscal, una serie de homologación preparada y accesos habilitados en el servidor.</small> : null}
      {readiness.parameters ? <details><summary>Parámetros y puntos de venta disponibles para revisión</summary>{Object.entries(readiness.parameters).map(([name, rows]) => <div key={name}><h3>{PARAMETER_LABELS[name] || name}</h3><ul>{rows.map((row, index) => { const value = row && typeof row === "object" ? row as Record<string, unknown> : {}; const id = value.id ?? value.Id ?? value.Nro ?? value.code ?? ""; const label = value.description ?? value.Desc ?? value.descripcion ?? value.name ?? value.Tipo ?? "Dato consultado"; return <li key={index}>{String(id)} · {String(label)}</li>; })}</ul></div>)}</details> : <p>Sin parámetros remotos disponibles. No se asignan puntos de venta, tipos ni permisos por defecto.</p>}
    </div> : null}
  </section>;
}
