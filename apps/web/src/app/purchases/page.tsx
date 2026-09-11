import { Suspense } from "react";

import { PurchasesScreen } from "@/features/purchases/components/purchases-screen";


export default function PurchasesPage() {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando compras" />}>
      <PurchasesScreen />
    </Suspense>
  );
}
