import type { Metadata } from "next";
import SitioPublico from "@/components/SitioPublico";

export const metadata: Metadata = {
  title: "Nomira — Software para despachos de abogados y notarías en México",
  description: "Liquidaciones LFT, agenda con revisión de estrados, portal para su cliente, cobranza, nómina, evidencia, AFORE, prospectos y escrituración para notarías. Contrate solo los módulos que necesita.",
  openGraph: {
    title: "Nomira — Cada prestación, en claro",
    description: "Software para despachos y notarías: liquidaciones, agenda, estrados, portal del cliente y más.",
    type: "website", locale: "es_MX", siteName: "Nomira",
  },
};

export default function Inicio() {
  return <SitioPublico />;
}
