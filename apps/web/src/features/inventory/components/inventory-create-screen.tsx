"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useClinic } from "@/features/clinic/clinic-context";
import { InventoryItemForm } from "@/features/inventory/components/inventory-item-form";
import {
  getInitialInventoryFormState,
  inventoryFormToCreatePayload,
  InventoryFormState,
  validateInventoryForm,
} from "@/features/inventory/components/inventory-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { createInventoryItem } from "@/services/inventory";

export function InventoryCreateScreen() {
  const router = useRouter();
  const { preferences } = useClinic();
  const [formState, setFormState] = useState<InventoryFormState>(
    getInitialInventoryFormState(preferences),
  );
  const [manualSalePriceOverride, setManualSalePriceOverride] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [flowMessage, setFlowMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validateInventoryForm(formState);
    if (validationMessage) {
      setFlowMessage(validationMessage);
      return;
    }

    setIsSubmitting(true);
    setFlowMessage(null);

    try {
      const response = await createInventoryItem(
        inventoryFormToCreatePayload(formState, manualSalePriceOverride),
      );
      router.push(`/inventory/${response.data.id}`);
    } catch (error) {
      setIsSubmitting(false);
      setFlowMessage(getApiErrorMessage(error));
    }
  }

  return (
    <InventoryItemForm
      title="Nuevo item"
      subtitle="Agregar al inventario"
      formState={formState}
      onChange={setFormState}
      onSubmit={handleSubmit}
      onCancel={() => router.push("/inventory")}
      isSubmitting={isSubmitting}
      submitLabel="Crear item"
      flowMessage={flowMessage}
      manualSalePriceOverride={manualSalePriceOverride}
      onManualSalePriceOverrideChange={setManualSalePriceOverride}
    />
  );
}
