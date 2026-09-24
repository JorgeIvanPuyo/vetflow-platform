"use client";

import { FormEvent, useEffect, useState } from "react";
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

  useEffect(() => {
    if (!preferences) {
      return;
    }

    const fallbackDefaults = getInitialInventoryFormState(null);
    const tenantDefaults = getInitialInventoryFormState(preferences);
    setFormState((current) => ({
      ...current,
      purchase_tax_mode:
        current.purchase_tax_rate_percentage === fallbackDefaults.purchase_tax_rate_percentage
          ? tenantDefaults.purchase_tax_mode
          : current.purchase_tax_mode,
      purchase_tax_rate_percentage:
        current.purchase_tax_rate_percentage === fallbackDefaults.purchase_tax_rate_percentage
          ? tenantDefaults.purchase_tax_rate_percentage
          : current.purchase_tax_rate_percentage,
      profit_margin_percentage:
        current.profit_margin_percentage === fallbackDefaults.profit_margin_percentage
          ? tenantDefaults.profit_margin_percentage
          : current.profit_margin_percentage,
      sale_tax_rate_percentage:
        current.sale_tax_rate_percentage === fallbackDefaults.sale_tax_rate_percentage
          ? tenantDefaults.sale_tax_rate_percentage
          : current.sale_tax_rate_percentage,
    }));
  }, [preferences]);

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
