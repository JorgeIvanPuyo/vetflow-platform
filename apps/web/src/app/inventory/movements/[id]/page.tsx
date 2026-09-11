import { Suspense } from "react";

import { InventoryMovementDetail } from "@/features/inventory/components/inventory-movement-detail";

export default function InventoryMovementDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando movimiento" />}>
      <InventoryMovementDetail movementId={params.id} />
    </Suspense>
  );
}
