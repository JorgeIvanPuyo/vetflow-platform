import Link from "next/link";

export default function HelpNotFound() {
  return <section className="empty-state"><h1>No encontramos esta guía</h1><p>Busca otra tarea en el Centro de ayuda.</p><Link className="primary-button" href="/help">Volver al Centro de ayuda</Link></section>;
}
