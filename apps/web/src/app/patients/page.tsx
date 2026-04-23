import { PatientsScreen } from "@/features/patients/components/patients-screen";

export default function PatientsPage() {
  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">Patients</p>
        <h1 className="page-title">Patient registry</h1>
        <p className="page-subtitle">
          List and creation flow connected to <code>/api/v1/patients</code>.
        </p>
      </section>

      <PatientsScreen />
    </div>
  );
}
