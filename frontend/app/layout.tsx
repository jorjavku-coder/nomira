import type { Metadata, Viewport } from "next";
import "@fontsource-variable/inter";
import "@fontsource-variable/montserrat";
import "./globals.css";
import IndicadorCarga from "@/components/CargaNomira";
import { RegistrarApp } from "@/components/AppInstalable";

export const metadata: Metadata = {
  title: "Nomira — Cada prestación, en claro",
  description: "Software para despachos jurídicos en México: agenda, clientes, cálculos laborales, tesis y portal para sus clientes.",
  applicationName: "Nomira",
  appleWebApp: { capable: true, title: "Nomira", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = { themeColor: "#0F263C", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-MX">
      <body>{children}<IndicadorCarga /><RegistrarApp /></body>
    </html>
  );
}
