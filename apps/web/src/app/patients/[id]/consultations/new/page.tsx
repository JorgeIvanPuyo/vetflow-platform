import { ConsultationWorkflow } from "@/features/consultations/components/consultation-workflow";

type NewConsultationPageProps = {
  params: {
    id: string;
  };
};

export default function NewConsultationPage({ params }: NewConsultationPageProps) {
  return <ConsultationWorkflow mode="new" patientId={params.id} />;
}
