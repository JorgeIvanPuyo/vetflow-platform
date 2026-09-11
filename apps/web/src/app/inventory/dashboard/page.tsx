import { Suspense } from "react";

import { InventoryDashboardScreen } from "@/features/inventory/components/inventory-dashboard-screen";

export default function InventoryDashboardPage() {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando dashboard de inventario" />}>
      <InventoryDashboardScreen />
    </Suspense>
  );
}
