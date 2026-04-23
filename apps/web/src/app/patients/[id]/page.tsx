import { PatientDetail } from "@/features/patients/components/patient-detail";

type PatientDetailPageProps = {
  params: {
    id: string;
  };
};

export default function PatientDetailPage({ params }: PatientDetailPageProps) {
  return <PatientDetail patientId={params.id} />;
}
