import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Conector de Nomira para Claude — tesis, finiquitos y plazos en su IA",
  description: "Conecte Claude con Nomira: busque tesis del Semanario Judicial, calcule finiquitos con la LFT y cuente plazos en días hábiles, gratis.",
  alternates: { canonical: "/conector-claude" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
