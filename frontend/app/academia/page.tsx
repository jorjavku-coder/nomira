"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AcademiaShell, Barra, SesionEnVivo, TarjetaCurso } from "@/components/academia";
import { Aviso } from "@/components/ui";
import { api, fecha } from "@/lib/api";

/** Mi aprendizaje: continuar, asignados, disponibles, completados y próximas sesiones. */
export default function MiAprendizaje() {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get("/academia/inicio").then(setR).catch((e) => setError(e.message)); }, []);
  const Seccion = ({ titulo, children, vacio }: any) => (
    <section className="mb-8"><h2 className="mb-3 text-lg font-bold text-marino">{titulo}</h2>{vacio || children}</section>
  );
  const continuar = r?.continuar?.[0];
  return (
    <AcademiaShell>
      <h1 className="text-3xl font-extrabold text-marino">Mi aprendizaje</h1>
      <p className="mb-5 mt-1 text-sm text-slate-500">Sus cursos asignados, lo que dejó a medias y lo que ya terminó.</p>
      <Aviso>{error}</Aviso>
      {!r && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {r && <>
        <div className="mb-6 grid grid-cols-3 gap-3 text-center">
          {[["Asignados", r.resumen.asignados], ["Obligatorios pendientes", r.resumen.obligatorios_pendientes], ["Completados", r.resumen.completados]].map(([t, v]) => (
            <div key={t as string} className="tarjeta p-3"><p className="text-2xl font-extrabold text-marino">{v}</p><p className="text-xs text-slate-500">{t}</p></div>))}
        </div>
        {continuar && (
          <section className="tarjeta mb-8 flex flex-wrap items-center gap-4 border-turquesa/40 bg-turquesa-50/40 p-5">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">Continuar aprendiendo</p>
              <h2 className="text-xl font-bold text-marino">{continuar.titulo}</h2>
              <div className="mt-2 max-w-md"><Barra valor={continuar.progreso.porcentaje} /></div>
              <p className="mt-1 text-xs text-slate-600">{continuar.progreso.texto}</p>
            </div>
            <Link className="btn-turquesa px-5 py-2.5 text-base" href={`/academia/lecciones/${continuar.ultima_leccion_id || continuar.progreso.siguiente_leccion_id}`}>Continuar curso</Link>
          </section>)}
        <Seccion titulo="Cursos asignados" vacio={r.asignados.length === 0 && <p className="tarjeta p-5 text-sm text-slate-500">No tiene cursos asignados por ahora. Explore los cursos disponibles abajo.</p>}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{r.asignados.map((c: any) => <TarjetaCurso key={c.id} c={c} />)}</div>
        </Seccion>
        {r.sesiones.length > 0 && (
          <Seccion titulo="Próximas sesiones en vivo">
            <div className="grid gap-3 md:grid-cols-2">
              {r.sesiones.map((s: any) => (
                <div key={s.id}><p className="mb-1 text-xs font-semibold text-slate-500">{s.curso}</p><SesionEnVivo s={s} />
                  {!s.enlace && <p className="mt-1 text-xs text-slate-500">El instructor compartirá el enlace.</p>}</div>))}
            </div>
          </Seccion>)}
        <Seccion titulo="Cursos disponibles" vacio={r.disponibles.length === 0 && <p className="text-sm text-slate-500">No hay más cursos disponibles por ahora.</p>}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{r.disponibles.map((c: any) => <TarjetaCurso key={c.id} c={c} />)}</div>
        </Seccion>
        <Seccion titulo="Completados" vacio={r.completados.length === 0 && <p className="text-sm text-slate-500">Cuando termine un curso aparecerá aquí con su diploma.</p>}>
          <ul className="tarjeta divide-y divide-crema-200">
            {r.completados.map((c: any) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
                <span><Link className="font-semibold text-marino hover:underline" href={`/academia/cursos/${c.id}`}>{c.titulo}</Link>
                  <span className="block text-xs text-slate-500">Completado el {fecha(c.completado_en)}</span></span>
                <button className="btn-sec" onClick={() => api.descargar(`/academia/constancias/${c.avance_id}`, c.reconocimiento === "constancia" ? "constancia.pdf" : "diploma.pdf").catch((e) => setError(e.message))}>{c.reconocimiento === "constancia" ? "Descargar constancia" : "Descargar diploma"}</button>
              </li>))}
          </ul>
        </Seccion>
      </>}
    </AcademiaShell>
  );
}
