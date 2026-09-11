import { PurchaseReturnDetailScreen } from "@/features/purchases/components/purchase-return-detail-screen";

type PageProps = { params: { id: string } };

export default function PurchaseReturnDetailPage({ params }: PageProps) {
  return <PurchaseReturnDetailScreen returnId={params.id} />;
}
