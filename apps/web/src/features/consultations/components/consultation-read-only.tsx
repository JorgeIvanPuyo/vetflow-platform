"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getConsultation } from "@/services/consultations";
import { getApiErrorMessage } from "@/lib/api";
import type { Consultation } from "@/types/api";

export function ConsultationReadOnly({ consultationId }: { consultationId: string }) {
  const [consultation, setConsultation] = useState<Consultation | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    getConsultation(consultationId).then((response) => {
      if (current) setConsultation(response.data);
    }).catch((value) => { if (current) setError(getApiErrorMessage(value)); });
    return () => { current = false; };
  }, [consultationId]);
  if (error) return <div className="error-state">{error}</div>;
  if (!consultation) return <div className="loading-state">Cargando consulta...</div>;
  return <section className="panel page-stack">
    <Link href={`/patients/${consultation.patient_id}`}>Volver al paciente</Link>
    <h1>Consulta · Solo lectura</h1>
    <p>La información clínica solo puede modificarla el personal clínico.</p>
    <dl className="detail-grid">
      {([
        ["Responsable", consultation.attending_user_name],
        ["Fecha", consultation.visit_date],
        ["Estado", consultation.status],
        ["Motivo", consultation.reason],
        ["Anamnesis", consultation.anamnesis],
        ["Síntomas", consultation.symptoms],
        ["Diagnóstico presuntivo", consultation.presumptive_diagnosis],
        ["Diagnóstico final", consultation.final_diagnosis],
        ["Examen clínico", consultation.clinical_exam],
        ["Hallazgos", consultation.physical_exam_findings],
        ["Plan diagnóstico", consultation.diagnostic_plan],
        ["Resultados", consultation.diagnostic_results],
        ["Plan terapéutico", consultation.therapeutic_plan],
        ["Notas terapéuticas", consultation.therapeutic_plan_notes],
        ["Indicaciones", consultation.indications],
        ["Próximo control", consultation.next_control_date],
        ["Resumen", consultation.consultation_summary],
      ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || "Sin registro"}</dd></div>)}
    </dl>
  </section>;
}
