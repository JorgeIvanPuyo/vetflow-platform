import { AppointmentDetail } from "@/features/agenda/components/appointment-detail";

type AppointmentDetailPageProps = {
  params: {
    id: string;
  };
};

export default function AppointmentDetailPage({
  params,
}: AppointmentDetailPageProps) {
  return <AppointmentDetail appointmentId={params.id} />;
}
