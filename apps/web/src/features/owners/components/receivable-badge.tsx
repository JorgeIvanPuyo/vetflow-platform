import Link from "next/link";

export function ReceivableBadge({ ownerId, hasActiveReceivable, forPatient = false }: {
  ownerId: string;
  hasActiveReceivable: boolean | null | undefined;
  forPatient?: boolean;
}) {
  if (hasActiveReceivable !== true) return null;
  const label = forPatient ? "Propietario con saldo pendiente" : "Saldo pendiente";
  return <Link className="badge badge--warning receivable-badge" href={`/owners/${ownerId}/receivables`}
    aria-label={`${label}. Ver cuenta corriente del propietario`}>{label}</Link>;
}
