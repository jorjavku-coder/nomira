import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Centro legal — Nomira",
  description: "Términos y condiciones, aviso de privacidad, cookies, anexo de tratamiento y solicitudes de derechos ARCO de Nomira.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
