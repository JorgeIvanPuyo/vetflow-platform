import { Suspense } from "react";

import { PurchaseDashboardScreen } from "@/features/purchases/components/purchase-dashboard-screen";


export default function PurchaseDashboardPage() {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando dashboard de compras" />}>
      <PurchaseDashboardScreen />
    </Suspense>
  );
}
