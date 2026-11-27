import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Descargue la app de Nomira para Android y iPhone",
  description: "Instale Nomira en su celular: su agenda, sus clientes y sus cálculos laborales con un toque, en pantalla completa.",
  alternates: { canonical: "/descargar" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
