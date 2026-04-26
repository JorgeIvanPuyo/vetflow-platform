import type { Metadata } from "next";

import { AuthenticatedShell } from "@/features/auth/components/authenticated-shell";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "VetClinic",
  description: "Plataforma clínica veterinaria",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>
        <AuthenticatedShell>{children}</AuthenticatedShell>
      </body>
    </html>
  );
}
