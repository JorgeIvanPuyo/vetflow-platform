import { SupplierDetailScreen } from "@/features/suppliers/components/supplier-detail-screen";


type PageProps = { params: { id: string } };

export default function SupplierDetailPage({ params }: PageProps) {
  return <SupplierDetailScreen supplierId={params.id} />;
}
