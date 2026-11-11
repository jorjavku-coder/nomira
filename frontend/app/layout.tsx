import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quincena Clara",
  description: "Análisis de comprobantes de nómina y cálculo de prestaciones por quincena",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-MX">
      <body>{children}</body>
    </html>
  );
}
