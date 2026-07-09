"use client";

import { FormEvent, useCallback, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import {
  createPreventiveCare,
  deletePreventiveCare,
  updatePreventiveCare,
} from "@/services/preventive-care";
import type { PreventiveCare } from "@/types/api";

import {
  PreventiveCareFormState,
  createInitialPreventiveCareFormState,
  toPreventiveCareFormState,
  toPreventiveCarePayload,
} from "../components/preventive-care/preventive-care-form";

export type PreventiveCareFormMode = "create" | "edit";

type UsePreventiveCareParams = {
  patientId: string;
  /** Se llama tras crear/editar/eliminar con éxito (recargar detalle + mensaje). */
  onChanged: (successMessage: string) => void | Promise<void>;
};

export function usePreventiveCare({ patientId, onChanged }: UsePreventiveCareParams) {
  const [formMode, setFormMode] = useState<PreventiveCareFormMode | null>(null);
  const [editingRecord, setEditingRecord] = useState<PreventiveCare | null>(null);
  const [formState, setFormState] = useState<PreventiveCareFormState>(
    createInitialPreventiveCareFormState,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [recordToDelete, setRecordToDelete] = useState<PreventiveCare | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const openCreate = useCallback(() => {
    setEditingRecord(null);
    setFormState(createInitialPreventiveCareFormState());
    setFormError(null);
    setFormMode("create");
  }, []);

  const openEdit = useCallback((record: PreventiveCare) => {
    setEditingRecord(record);
    setFormState(toPreventiveCareFormState(record));
    setFormError(null);
    setFormMode("edit");
  }, []);

  const closeForm = useCallback(() => {
    if (isSubmitting) {
      return;
    }
    setFormMode(null);
    setEditingRecord(null);
    setFormError(null);
  }, [isSubmitting]);

  const submitForm = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      const payload = toPreventiveCarePayload(formState);
      setIsSubmitting(true);
      setFormError(null);

      try {
        if (formMode === "edit" && editingRecord) {
          await updatePreventiveCare(editingRecord.id, payload);
        } else {
          await createPreventiveCare(patientId, payload);
        }

        setIsSubmitting(false);
        setFormMode(null);
        setEditingRecord(null);
        await onChanged(
          formMode === "edit"
            ? "Registro preventivo actualizado correctamente."
            : "Registro preventivo agregado correctamente.",
        );
      } catch (error) {
        setIsSubmitting(false);
        setFormError(getApiErrorMessage(error));
      }
    },
    [editingRecord, formMode, formState, onChanged, patientId],
  );

  const openDelete = useCallback((record: PreventiveCare) => {
    setRecordToDelete(record);
    setDeleteError(null);
  }, []);

  const closeDelete = useCallback(() => {
    if (isDeleting) {
      return;
    }
    setRecordToDelete(null);
    setDeleteError(null);
  }, [isDeleting]);

  const confirmDelete = useCallback(async () => {
    if (!recordToDelete) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deletePreventiveCare(recordToDelete.id);
      setIsDeleting(false);
      setRecordToDelete(null);
      await onChanged("Registro preventivo eliminado correctamente.");
    } catch (error) {
      setIsDeleting(false);
      setDeleteError(getApiErrorMessage(error));
    }
  }, [onChanged, recordToDelete]);

  return {
    // formulario (crear/editar)
    formMode,
    editingRecord,
    formState,
    setFormState,
    isSubmitting,
    formError,
    openCreate,
    openEdit,
    closeForm,
    submitForm,
    // borrado
    recordToDelete,
    isDeleting,
    deleteError,
    openDelete,
    closeDelete,
    confirmDelete,
  };
}
