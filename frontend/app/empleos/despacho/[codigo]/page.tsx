"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CabeceraEmpleos, PieEmpleos, TarjetaVacante, pedirPublico } from "@/components/empleos";
import { Aviso } from "@/components/ui";

export default function PaginaDespacho() {
  const { codigo } = useParams<{ codigo: string }>();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { pedirPublico(`/empleos/despacho/${codigo}`).then(setD).catch((e) => setError(e.message)); }, [codigo]);
  return (
    <>
      <CabeceraEmpleos />
      <main className="mx-auto max-w-5xl px-5 py-8">
        <Aviso>{error}</Aviso>
        {d && <>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Trabaja con nosotros</p>
          <h1 className="font-marca text-3xl font-extrabold text-marino sm:text-4xl">{d.despacho.nombre}</h1>
          {(d.despacho.ciudad || d.despacho.sitio_web) && <p className="mt-1 text-sm text-slate-600">{d.despacho.ciudad}
            {d.despacho.sitio_web && <>{d.despacho.ciudad ? " · " : ""}<a href={d.despacho.sitio_web} target="_blank" rel="noopener noreferrer nofollow" className="underline">{d.despacho.sitio_web.replace(/^https?:\/\//, "")}</a></>}</p>}
          {d.despacho.descripcion && <p className="mt-3 max-w-3xl whitespace-pre-wrap text-slate-700">{d.despacho.descripcion}</p>}
          <h2 className="mt-8 text-lg font-bold text-marino">Vacantes abiertas ({d.vacantes.length})</h2>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">{d.vacantes.map((v: any) => <TarjetaVacante key={v.codigo} v={v} despacho={false} />)}</div>
          {!d.vacantes.length && <p className="tarjeta mt-2 p-6 text-center text-slate-600">Por ahora no hay vacantes abiertas. Vuelve pronto.</p>}
        </>}
      </main>
      <PieEmpleos />
    </>
  );
}
