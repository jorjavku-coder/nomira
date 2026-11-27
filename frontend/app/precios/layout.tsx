import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Precios de Nomira — arme su plan y reciba su cotización al instante",
  description: "Paquetes y módulos de Nomira para despachos jurídicos en México. Elija lo que necesita, vea el total con IVA y reciba su cotización formal para pagarla en línea.",
  alternates: { canonical: "/precios" },
  openGraph: { title: "Precios de Nomira", type: "website", locale: "es_MX", siteName: "Nomira" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
