"use client";

import { PatientSelector } from "@/components/patient-selector";
import { SaleOwnerSelector } from "./sale-owner-selector";

export type SaleCustomer = {
  ownerId: string;
  ownerName: string;
  patientId: string;
  patientName: string;
};

export function SaleCustomerSelector({ value, onChange }: { value: SaleCustomer; onChange: (value: SaleCustomer) => void }) {
  return <>
    <SaleOwnerSelector disabled={Boolean(value.patientId)} ownerId={value.ownerId} ownerName={value.ownerName} onSelect={(owner) => {
      const ownerId = owner?.id ?? "";
      onChange({ ...value, ownerId, ownerName: owner?.full_name ?? "",
        patientId: ownerId === value.ownerId ? value.patientId : "",
        patientName: ownerId === value.ownerId ? value.patientName : "" });
    }} />
    <PatientSelector ownerId={value.ownerId} idPrefix="sale-patient" patientId={value.patientId} patientName={value.patientName}
      onSelect={(patient) => {
        if (patient && value.ownerId && patient.owner_id !== value.ownerId) return;
        onChange(patient ? {
        ownerId: patient.owner_id, ownerName: patient.owner_name ?? "",
        patientId: patient.id, patientName: patient.name,
      } : { ...value, patientId: "", patientName: "" });
      }} />
    <p className="panel-note">Limpia el paciente para cambiar de propietario. Sin propietario puedes buscar cualquier paciente.</p>
  </>;
}
