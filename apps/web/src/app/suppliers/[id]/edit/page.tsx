import { SupplierFormScreen } from "@/features/suppliers/components/supplier-form-screen";


type PageProps = { params: { id: string } };

export default function EditSupplierPage({ params }: PageProps) {
  return <SupplierFormScreen supplierId={params.id} />;
}
