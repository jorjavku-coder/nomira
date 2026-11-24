import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Calculadora de finiquito y liquidación 2026 (LFT) gratis — Nomira",
  description: "Calcule gratis finiquito, liquidación, prima de antigüedad, indemnización de 3 meses y 20 días, y salarios caídos conforme a la Ley Federal del Trabajo, con la operación y el artículo de cada concepto.",
  alternates: { canonical: "/calculadora-finiquito" },
  openGraph: { title: "Calculadora de finiquito y liquidación (LFT) — Nomira", type: "website", locale: "es_MX", siteName: "Nomira" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
