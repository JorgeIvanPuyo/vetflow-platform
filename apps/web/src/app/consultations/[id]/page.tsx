import { ConsultationDetail } from "@/features/consultations/components/consultation-detail";

type ConsultationDetailPageProps = {
  params: {
    id: string;
  };
};

export default function ConsultationDetailPage({
  params,
}: ConsultationDetailPageProps) {
  return <ConsultationDetail consultationId={params.id} />;
}
