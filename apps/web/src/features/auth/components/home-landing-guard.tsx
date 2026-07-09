"use client";

import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";

// Scoped roles (e.g. contador) must not land on the dashboard home; send them
// to their only allowed module.
const SCOPED_ROLE_HOME: Record<string, string> = {
  contador: "/accounting",
};

export function HomeLandingGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { role, isLoading } = useCurrentUser();
  const redirectTo = role ? SCOPED_ROLE_HOME[role] : undefined;

  useEffect(() => {
    if (!isLoading && redirectTo) {
      router.replace(redirectTo);
    }
  }, [isLoading, redirectTo, router]);

  if (redirectTo) {
    return null;
  }

  return <>{children}</>;
}
