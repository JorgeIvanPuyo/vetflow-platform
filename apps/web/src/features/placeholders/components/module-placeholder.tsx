import { Construction } from "lucide-react";

export function ModulePlaceholder({ moduleName }: { moduleName: string }) {
  return (
    <section className="placeholder-card" aria-labelledby="placeholder-title">
      <span className="icon-bubble icon-bubble--warning">
        <Construction aria-hidden="true" size={28} />
      </span>
      <p className="eyebrow">{moduleName}</p>
      <h1 id="placeholder-title">Módulo en construcción</h1>
      <p>Esta funcionalidad estará disponible en una próxima versión.</p>
    </section>
  );
}
