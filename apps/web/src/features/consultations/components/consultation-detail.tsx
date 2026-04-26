"use client";

import { ConsultationWorkflow } from "@/features/consultations/components/consultation-workflow";

type ConsultationDetailProps = {
  consultationId: string;
};

export function ConsultationDetail({ consultationId }: ConsultationDetailProps) {
  return <ConsultationWorkflow consultationId={consultationId} mode="edit" />;
}
