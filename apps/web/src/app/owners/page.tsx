import { OwnersScreen } from "@/features/owners/components/owners-screen";

export default function OwnersPage() {
  return (
    <div className="page-stack">
      <section className="screen-heading">
        <p className="eyebrow">Clientes</p>
        <h1>Propietarios</h1>
        <p>Directorio de personas responsables y contactos clínicos.</p>
      </section>

      <OwnersScreen />
    </div>
  );
}
