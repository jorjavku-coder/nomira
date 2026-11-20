import type { Metadata } from "next";

export const metadata: Metadata = { title: "Verificar diploma — Nomira Academia", robots: { index: false, follow: false } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
