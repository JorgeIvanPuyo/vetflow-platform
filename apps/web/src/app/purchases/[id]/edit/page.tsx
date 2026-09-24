import { PurchaseFormScreen } from "@/features/purchases/components/purchase-form-screen";


type PageProps = { params: { id: string } };

export default function EditPurchasePage({ params }: PageProps) {
  return <PurchaseFormScreen purchaseId={params.id} />;
}
