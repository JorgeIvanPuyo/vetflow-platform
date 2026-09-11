import { SaleDetailScreen } from "@/features/sales/components/sale-detail-screen";

type Props = { params: { id: string } };
export default function SaleDetailPage({ params }: Props) { return <SaleDetailScreen saleId={params.id} />; }
