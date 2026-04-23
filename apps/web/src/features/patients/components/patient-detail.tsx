"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { getPatient } from "@/services/patients";
import type { Patient } from "@/types/api";

type PatientDetailProps = {
  patientId: string;
};

type PatientDetailState = {
  isLoading: boolean;
  patient: Patient | null;
  errorMessage: string | null;
};

const initialState: PatientDetailState = {
  isLoading: true,
  patient: null,
  errorMessage: null,
};

export function PatientDetail({ patientId }: PatientDetailProps) {
  const [state, setState] = useState<PatientDetailState>(initialState);

  useEffect(() => {
    let isMounted = true;

    async function loadPatient() {
      try {
        const response = await getPatient(patientId);

        if (!isMounted) {
          return;
        }

        setState({
          isLoading: false,
          patient: response.data,
          errorMessage: null,
        });
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message =
          error instanceof ApiClientError
            ? error.message
            : "Could not load patient";

        setState({
          isLoading: false,
          patient: null,
          errorMessage: message,
        });
      }
    }

    void loadPatient();

    return () => {
      isMounted = false;
    };
  }, [patientId]);

  if (state.isLoading) {
    return <div className="panel">Loading patient details...</div>;
  }

  if (state.errorMessage) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!state.patient) {
    return <div className="empty-state">Patient not found.</div>;
  }

  const patient = state.patient;

  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">
          <Link href="/patients">Patients</Link> / Detail
        </p>
        <h1 className="page-title">{patient.name}</h1>
        <p className="page-subtitle">
          {patient.species}
          {patient.breed ? ` · ${patient.breed}` : ""}
        </p>
      </section>

      <section className="panel">
        <dl className="detail-grid">
          <div>
            <dt>Species</dt>
            <dd>{patient.species}</dd>
          </div>
          <div>
            <dt>Breed</dt>
            <dd>{patient.breed ?? "Not provided"}</dd>
          </div>
          <div>
            <dt>Sex</dt>
            <dd>{patient.sex ?? "Not provided"}</dd>
          </div>
          <div>
            <dt>Estimated age</dt>
            <dd>{patient.estimated_age ?? "Not provided"}</dd>
          </div>
          <div>
            <dt>Weight</dt>
            <dd>{patient.weight_kg ? `${patient.weight_kg} kg` : "Not provided"}</dd>
          </div>
          <div>
            <dt>Owner ID</dt>
            <dd>{patient.owner_id}</dd>
          </div>
          <div>
            <dt>Allergies</dt>
            <dd>{patient.allergies ?? "None registered"}</dd>
          </div>
          <div>
            <dt>Chronic conditions</dt>
            <dd>{patient.chronic_conditions ?? "None registered"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
