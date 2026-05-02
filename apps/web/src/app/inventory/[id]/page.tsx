import { InventoryDetail } from "@/features/inventory/components/inventory-detail";

export default function InventoryDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <InventoryDetail itemId={params.id} />;
}
