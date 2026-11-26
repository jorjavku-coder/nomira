import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Aliados del Club Nomira — lleve su marca a los despachos de abogados",
  description: "Ofrezca un beneficio a los despachos de abogados y notarías que usan Nomira.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
