import { PurchaseReturnFormScreen } from "@/features/purchases/components/purchase-return-form-screen";

type PageProps = { params: { id: string } };

export default function NewPurchaseReturnPage({ params }: PageProps) {
  return <PurchaseReturnFormScreen purchaseId={params.id} />;
}
