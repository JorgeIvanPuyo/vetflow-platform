import { Suspense } from "react";

import { InventoryMovementsScreen } from "@/features/inventory/components/inventory-movements-screen";

export default function InventoryMovementsPage() {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando movimientos" />}>
      <InventoryMovementsScreen />
    </Suspense>
  );
}
