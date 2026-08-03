import { InventoryBulkOperationDetail } from "@/features/inventory/components/inventory-bulk-operation-detail";

type PageProps = {
  params: {
    id: string;
  };
};

export default function InventoryBulkOperationDetailPage({ params }: PageProps) {
  return <InventoryBulkOperationDetail operationId={params.id} />;
}
