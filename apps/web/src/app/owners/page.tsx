import { OwnersScreen } from "@/features/owners/components/owners-screen";

export default function OwnersPage() {
  return (
    <div className="page-stack">
      <section className="hero-card">
        <p className="page-subtitle">Owners</p>
        <h1 className="page-title">Owner directory</h1>
        <p className="page-subtitle">
          List and creation flow connected to <code>/api/v1/owners</code>.
        </p>
      </section>

      <OwnersScreen />
    </div>
  );
}
