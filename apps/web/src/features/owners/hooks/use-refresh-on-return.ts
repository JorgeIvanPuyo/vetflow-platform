"use client";

import { useEffect } from "react";

/** Revalidate derived signals after returning from a sale, without polling. */
export function useRefreshOnReturn(load: () => unknown) {
  useEffect(() => {
    const refresh = () => { void load(); };
    window.addEventListener("pageshow", refresh);
    window.addEventListener("focus", refresh);
    return () => {
      window.removeEventListener("pageshow", refresh);
      window.removeEventListener("focus", refresh);
    };
  }, [load]);
}
