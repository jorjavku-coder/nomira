import type { Metadata } from "next";
import SitioPublico from "@/components/SitioPublico";

export const metadata: Metadata = {
  title: "Nomira — Análisis de comprobantes de nómina y prestaciones por quincena",
  description: "Nomira lee comprobantes de nómina en PDF, suma solo las prestaciones de su catálogo autorizado y entrega el desglose por quincena, con cada cifra ligada a su comprobante.",
  openGraph: {
    title: "Nomira — Cada prestación, en claro",
    description: "Desglose de prestaciones por quincena a partir de comprobantes de nómina en PDF, con trazabilidad completa.",
    type: "website", locale: "es_MX", siteName: "Nomira",
  },
};

export default function Inicio() {
  return <SitioPublico />;
}
