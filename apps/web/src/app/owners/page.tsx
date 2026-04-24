import { OwnersScreen } from "@/features/owners/components/owners-screen";

export default function OwnersPage() {
  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">Propietarios</p>
        <h1 className="page-title">Directorio de propietarios</h1>
        <p className="page-subtitle">
          Lista y creación conectadas a <code>/api/v1/owners</code>.
        </p>
      </section>

      <OwnersScreen />
    </div>
  );
}
