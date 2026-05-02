import { FollowUpDetail } from "@/features/follow-ups/components/follow-up-detail";

type FollowUpDetailPageProps = {
  params: {
    id: string;
  };
};

export default function FollowUpDetailPage({
  params,
}: FollowUpDetailPageProps) {
  return <FollowUpDetail followUpId={params.id} />;
}
