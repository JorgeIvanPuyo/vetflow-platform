import { Suspense } from "react";

import { InventoryDetail } from "@/features/inventory/components/inventory-detail";

export default function InventoryDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <Suspense fallback={<div className="loading-card" aria-label="Cargando item de inventario" />}>
      <InventoryDetail itemId={params.id} />
    </Suspense>
  );
}
