import type { Metadata } from "next";

import { AppHeader } from "@/components/layout/app-header";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Vetflow",
  description: "Plataforma clínica veterinaria multi-tenant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>
        <div className="app-shell">
          <AppHeader />
          <main className="page-container">{children}</main>
        </div>
      </body>
    </html>
  );
}
