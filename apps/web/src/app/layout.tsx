import type { Metadata } from "next";

import { AppHeader } from "@/components/layout/app-header";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Vetflow",
  description: "Multi-tenant veterinary clinical platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <AppHeader />
          <main className="page-container">{children}</main>
        </div>
      </body>
    </html>
  );
}
