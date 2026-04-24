import { ExamDetail } from "@/features/exams/components/exam-detail";

type ExamDetailPageProps = {
  params: {
    id: string;
  };
};

export default function ExamDetailPage({ params }: ExamDetailPageProps) {
  return <ExamDetail examId={params.id} />;
}
