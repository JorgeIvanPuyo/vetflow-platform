import { PurchaseDetailScreen } from "@/features/purchases/components/purchase-detail-screen";


type PageProps = { params: { id: string } };

export default function PurchaseDetailPage({ params }: PageProps) {
  return <PurchaseDetailScreen purchaseId={params.id} />;
}
