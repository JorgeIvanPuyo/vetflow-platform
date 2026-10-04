"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";
import { getApiErrorMessage } from "@/lib/api";
import { canOperateClinic } from "@/lib/permissions";
import { updateClinicPreferences } from "@/services/clinic";
import type { TenantPreferences } from "@/types/api";

import { clinicCalendarDate, cutoffChangeWarning, startDateError, startDateLabel } from "./receivables-settings-helpers";

export function ReceivablesSettingsSection({ preferences, timezone, onSaved }: {
  preferences: TenantPreferences;
  timezone: string;
  onSaved: (preferences: TenantPreferences) => void;
}) {
  const { role } = useCurrentUser();
  const canEdit = canOperateClinic(role);
  const cutoff = preferences.receivables_tracking_started_at ?? null;
  let activeDate = "", today = "", timezoneError: string | null = null;
  try {
    today = clinicCalendarDate(new Date(), timezone);
    activeDate = cutoff ? clinicCalendarDate(cutoff, timezone) : "";
  } catch {
    timezoneError = "No pudimos interpretar la fecha en la zona horaria de la clínica.";
  }
  const [selectedDate, setSelectedDate] = useState(activeDate);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmationDate, setConfirmationDate] = useState<string | null>(null);
  const saving = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const warning = activeDate ? cutoffChangeWarning(selectedDate, activeDate) : null;
  const validation = selectedDate ? startDateError(selectedDate, today) : null;

  useEffect(() => { setSelectedDate(activeDate); }, [activeDate]);
  useEffect(() => {
    if (!confirmationDate) return;
    const previousFocus = document.activeElement;
    const element = dialog.current;
    element?.showModal();
    return () => {
      element?.close();
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, [confirmationDate]);

  function selectDate(value: string) {
    if (saving.current || !canEdit) return;
    setSelectedDate(value); setError(null); setSuccess(null);
  }

  async function save(value: string) {
    if (saving.current || !canEdit || timezoneError) return;
    // Recheck today at the actual submit, including an open confirmation dialog.
    const invalid = startDateError(value, clinicCalendarDate(new Date(), timezone));
    if (invalid) { setError(invalid); setConfirmationDate(null); return; }
    saving.current = true; setIsSaving(true); setError(null); setSuccess(null);
    try {
      const response = await updateClinicPreferences({ receivables_tracking_start_date: value });
      onSaved(response.data);
      setSelectedDate(clinicCalendarDate(response.data.receivables_tracking_started_at!, timezone));
      setSuccess("Configuración guardada.");
    } catch (value) {
      setError(getApiErrorMessage(value));
    } finally {
      saving.current = false; setIsSaving(false); setConfirmationDate(null);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (saving.current || confirmationDate || !canEdit || timezoneError) return;
    const invalid = startDateError(selectedDate, clinicCalendarDate(new Date(), timezone));
    if (invalid) { setError(invalid); return; }
    if (cutoff && selectedDate === activeDate) return;
    if (cutoff) { setConfirmationDate(selectedDate); return; }
    void save(selectedDate);
  }

  return <section className="receivables-settings" aria-labelledby="receivables-settings-title">
    <h2 id="receivables-settings-title">Cuentas por cobrar</h2>
    <p className="receivables-settings__status" role="status">{cutoff ? `Activo desde ${activeDate ? startDateLabel(activeDate) : "fecha no disponible"}` : "No configurado"}</p>
    <p>Vetflow comenzará a controlar saldos pendientes desde esta fecha. Las ventas anteriores no se incluirán automáticamente en la cuenta corriente.</p>
    <form onSubmit={submit}>
      <fieldset className="receivables-settings__fields" disabled={!canEdit || isSaving || Boolean(timezoneError)}>
        <label className="field" htmlFor="receivables-start-date"><span>Fecha de inicio</span><input id="receivables-start-date" type="date" required max={today} value={selectedDate} aria-describedby="receivables-date-help receivables-date-warning" aria-invalid={Boolean(validation)} onChange={(event) => selectDate(event.target.value)} /></label>
        <p id="receivables-date-help">Se toma el inicio del día en la zona horaria de la clínica: {timezone}.</p>
        <div id="receivables-date-warning" aria-live="polite">
          {validation ? <p className="error-state">{validation}</p> : warning ? <p className="purchase-reversal-warning">{warning}</p> : selectedDate && selectedDate < today ? <p>Las ventas confirmadas desde esta fecha que aún tengan saldo pendiente podrán aparecer en las cuentas por cobrar.</p> : null}
        </div>
        <div className="receivables-settings__actions">
          <button type="button" className="secondary-button" onClick={() => selectDate(clinicCalendarDate(new Date(), timezone))}>Empezar desde hoy</button>
          <button type="submit" className="primary-button" disabled={isSaving || !selectedDate || Boolean(validation) || Boolean(cutoff && selectedDate === activeDate)} aria-live="polite">{isSaving ? <><span className="vf-spinner vf-spinner--sm vf-spinner--button" aria-hidden="true" />Guardando…</> : cutoff ? "Guardar cambios" : "Guardar configuración"}</button>
        </div>
      </fieldset>
    </form>
    {!canEdit ? <p>Tu usuario no tiene permiso para modificar esta configuración.</p> : null}
    {timezoneError || error ? <p className="error-state" role="alert">{timezoneError ?? error}</p> : null}
    {success ? <p className="success-state" role="status">{success}</p> : null}
    {confirmationDate ? <dialog ref={dialog} className="panel sale-service-dialog receivables-settings-dialog" aria-labelledby="receivables-confirm-title" aria-describedby="receivables-confirm-help" onCancel={(event) => { event.preventDefault(); if (!saving.current) setConfirmationDate(null); }} onKeyDown={(event) => {
      if (event.key !== "Tab") return;
      const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)");
      if (!buttons.length) { event.preventDefault(); return; }
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    }}>
      <h2 id="receivables-confirm-title">Cambiar fecha de inicio</h2>
      <p id="receivables-confirm-help">Cambiar esta fecha puede modificar qué ventas aparecen en las cuentas por cobrar.</p>
      <p>Fecha actual: {startDateLabel(activeDate)} · Nueva fecha: {startDateLabel(confirmationDate)}</p>
      <p className="purchase-reversal-warning">{cutoffChangeWarning(confirmationDate, activeDate)}</p>
      <div className="receivables-settings__actions">
        <button type="button" className="secondary-button" disabled={isSaving} autoFocus onClick={() => { if (!saving.current) setConfirmationDate(null); }}>Cancelar</button>
        <button type="button" className="primary-button" disabled={isSaving} aria-live="polite" onClick={() => void save(confirmationDate)}>{isSaving ? "Guardando…" : "Confirmar cambio"}</button>
      </div>
    </dialog> : null}
  </section>;
}
