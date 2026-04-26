import { OwnerDetail } from "@/features/owners/components/owner-detail";

export default function OwnerDetailPage({ params }: { params: { id: string } }) {
  return <OwnerDetail ownerId={params.id} />;
}
