import { OwnerAccountScreen } from "@/features/owners/components/owner-account-screen";

export default function OwnerAccountPage({ params }: { params: { id: string } }) {
  return <OwnerAccountScreen key={params.id} ownerId={params.id} />;
}
