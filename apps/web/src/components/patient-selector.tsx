"use client";

import { useCallback, useEffect, useState } from "react";

import { SearchSelector } from "@/components/search-selector";
import { getPatient, getPatients } from "@/services/patients";
import type { Patient } from "@/types/api";

export function patientLabel(patient: Patient) {
  return [patient.name, patient.species, patient.owner_name].filter(Boolean).join(" · ");
}

type Props = {
  ownerId?: string;
  patientId: string;
  patientName?: string;
  idPrefix: string;
  onSelect: (patient: Patient | null) => void;
};

export function PatientSelector({ ownerId = "", patientId, patientName = "", idPrefix, onSelect }: Props) {
  const loadPatients = useCallback((options: { search?: string; page: number; pageSize: number }) =>
    getPatients({ ...options, ...(ownerId ? { ownerId } : {}), sortBy: "name" }), [ownerId]);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  useEffect(() => {
    if (!patientId || selectedPatient?.id === patientId || patientName) return;
    let cancelled = false;
    getPatient(patientId).then(({ data }) => {
      if (!cancelled) setSelectedPatient(data);
    }).catch(() => { /* Preserve the saved ID if its label cannot be loaded. */ });
    return () => { cancelled = true; };
  }, [patientId, patientName, selectedPatient?.id]);

  return <SearchSelector key={ownerId || "all-patients"} selectedId={patientId}
    selectedLabel={selectedPatient?.id === patientId ? patientLabel(selectedPatient) : patientName}
    idPrefix={idPrefix} label="Paciente" plural="Pacientes" emptyLabel="Sin paciente seleccionado"
    loadPage={loadPatients} itemLabel={patientLabel}
    onSelect={(patient) => {
      if (patient && ownerId && patient.owner_id !== ownerId) return;
      setSelectedPatient(patient); onSelect(patient);
    }} />;
}
