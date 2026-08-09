import { PurchaseReturnFormScreen } from "@/features/purchases/components/purchase-return-form-screen";

type PageProps = { params: { id: string } };

export default function EditPurchaseReturnPage({ params }: PageProps) {
  return <PurchaseReturnFormScreen returnId={params.id} />;
}
