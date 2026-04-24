import { PatientsScreen } from "@/features/patients/components/patients-screen";

export default function PatientsPage() {
  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">Pacientes</p>
        <h1 className="page-title">Registro de pacientes</h1>
        <p className="page-subtitle">
          Lista y creación conectadas a <code>/api/v1/patients</code>.
        </p>
      </section>

      <PatientsScreen />
    </div>
  );
}
