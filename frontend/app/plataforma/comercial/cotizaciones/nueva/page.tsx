"use client";
import Link from "next/link";
import { ComercialShell, Constructor, useCatalogoCM } from "@/components/comercial";
import { Aviso } from "@/components/ui";

export default function NuevaCotizacion() {
  const [cat, error] = useCatalogoCM();
  return (
    <ComercialShell>
      <Link href="/plataforma/comercial/cotizaciones" className="text-sm text-turquesa-700 hover:underline">← Cotizaciones</Link>
      <h1 className="mb-4 mt-1 text-3xl font-extrabold text-marino">Nueva cotización</h1>
      <Aviso>{error}</Aviso>
      {cat ? <Constructor cat={cat} onGuardado={() => {}} /> : !error && <p className="text-sm text-slate-500">Cargando…</p>}
    </ComercialShell>
  );
}
