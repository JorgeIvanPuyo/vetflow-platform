"use client";

import { createContext, ReactNode, useContext, useLayoutEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { setPageReadHandler } from "@/lib/api";
import { PageReadRecovery, type ReadRecoveryState } from "./page-read-recovery";
import styles from "./page-read-boundary.module.css";

const RecoveryContext = createContext<{
  state: ReadRecoveryState;
  retry: () => void;
}>({ state: { phase: "idle", seconds: 0 }, retry: () => {} });

export function PageReadBoundary({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const routeKey = `${pathname}?${searchParams.toString()}`;
  const [value, setValue] = useState({
    state: { phase: "idle", seconds: 0 } as ReadRecoveryState,
    retry: () => {},
  });
  // Install before page passive effects start their GETs. Recreate on route change
  // (also on StrictMode effect replay), without remounting the page or its forms.
  useLayoutEffect(() => {
    const recovery = new PageReadRecovery();
    const unsubscribe = recovery.subscribe(state => setValue({ state, retry: () => { void recovery.retryNow(); } }));
    const unregister = setPageReadHandler(recovery.run);
    return () => { unregister(); unsubscribe(); recovery.dispose(); };
  }, [routeKey]);
  return <RecoveryContext.Provider value={value}>{children}</RecoveryContext.Provider>;
}

export function PageReadContent({ children }: { children: ReactNode }) {
  const { state, retry } = useContext(RecoveryContext);
  return <>
    <PageReadStatus state={state} retry={retry} />
    <div hidden={state.phase !== "idle"}>{children}</div>
  </>;
}

export function PageReadStatus({ state, retry }: { state: ReadRecoveryState; retry: () => void }) {
  if (state.phase === "idle") return null;
  const failed = state.phase === "failed";
  return <section className={styles.status} aria-label="Estado de conexión">
    <h2>{failed ? "No pudimos conectar con el servidor" : "Conectando con el servidor"}</h2>
    <p>{failed
      ? "El servidor no respondió después de varios intentos. Puedes intentar nuevamente en unos minutos. Si el problema continúa, comunícate con el administrador del sistema."
      : "Estamos cargando la información. El servidor puede tardar unos segundos en responder."}</p>
    <p role="status" aria-live="polite" aria-atomic="true">
      {state.phase === "waiting" ? `Reintento automático en ${state.seconds} s.`
        : state.phase === "retrying" ? "Reintentando…" : null}
    </p>
    <button className="secondary-button" type="button" disabled={state.phase === "retrying"} onClick={retry}>
      {failed ? "Reintentar" : "Recargar ahora"}
    </button>
  </section>;
}
