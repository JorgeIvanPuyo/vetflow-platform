import { SaleFormScreen } from "@/features/sales/components/sale-form-screen";

type Props = { params: { id: string } };
export default function EditSalePage({ params }: Props) { return <SaleFormScreen saleId={params.id} />; }
