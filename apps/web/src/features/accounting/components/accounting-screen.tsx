"use client";

import { Calculator, Construction } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";

export function AccountingScreen() {
  const router = useRouter();
  const { role, isLoading } = useCurrentUser();

  useEffect(() => {
    if (!isLoading && role && role !== "contador" && role !== "superadmin") {
      router.replace("/");
    }
  }, [isLoading, role, router]);

  return (
    <div className="page-stack">
      <section className="screen-heading list-page__header">
        <div>
          <h1>
            <Calculator aria-hidden="true" size={22} /> Contabilidad
          </h1>
          <p>Gestión contable de la clínica</p>
        </div>
      </section>

      <section className="panel empty-state" aria-live="polite">
        <Construction aria-hidden="true" size={40} />
        <h2>En construcción</h2>
        <p>Este módulo estará disponible próximamente.</p>
      </section>
    </div>
  );
}
