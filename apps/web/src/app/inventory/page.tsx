import { Suspense } from "react";

import { InventoryScreen } from "@/features/inventory/components/inventory-screen";

export default function InventoryPage() {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando inventario" />}>
      <InventoryScreen />
    </Suspense>
  );
}
