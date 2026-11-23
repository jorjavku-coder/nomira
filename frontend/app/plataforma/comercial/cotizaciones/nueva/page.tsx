"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ComercialShell, Constructor, useCatalogoCM } from "@/components/comercial";
import { Aviso } from "@/components/ui";
import { apiP } from "@/lib/plataforma";

export default function NuevaCotizacion() {
  const [cat, error] = useCatalogoCM();
  const [inicial, setInicial] = useState<any>(undefined);
  useEffect(() => {  // desde una oportunidad de Ventas: llega con los datos del prospecto y queda ligada
    const id = Number(new URLSearchParams(window.location.search).get("oportunidad"));
    if (!id) { setInicial(null); return; }
    apiP.get(`/ventas/oportunidades/${id}`).then((o) => setInicial({ oportunidad_id: o.id, contacto: o.contacto?.nombre, despacho: o.contacto?.despacho || o.contacto?.nombre,
      email: o.contacto?.email || "", telefono: o.contacto?.telefono || "", necesidad: o.titulo })).catch(() => setInicial(null));
  }, []);
  return (
    <ComercialShell>
      <Link href="/plataforma/comercial/cotizaciones" className="text-sm text-turquesa-700 hover:underline">← Cotizaciones</Link>
      <h1 className="mb-4 mt-1 text-3xl font-extrabold text-marino">Nueva cotización</h1>
      <Aviso>{error}</Aviso>
      {inicial?.oportunidad_id && <p className="mb-3 text-sm text-slate-600">Para la oportunidad <Link className="font-semibold text-turquesa-700 underline" href={`/plataforma/ventas/oportunidades/${inicial.oportunidad_id}`}>{inicial.necesidad}</Link>: al enviarse o pagarse, la oportunidad avanza sola.</p>}
      {cat && inicial !== undefined ? <Constructor cat={cat} inicial={inicial || undefined} onGuardado={() => {}} /> : !error && <p className="text-sm text-slate-500">Cargando…</p>}
    </ComercialShell>
  );
}
