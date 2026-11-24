import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Bolsa de trabajo jurídica · Nomira",
  description: "Vacantes para abogados, pasantes y personal de despachos en México. Postúlate en línea con tu CV.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-crema">{children}</div>;
}
