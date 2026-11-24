"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, leerSesion, mxn } from "@/lib/api";

export const CAUSA_CORTA: Record<string, string> = {
  renuncia: "Renuncia", mutuo_acuerdo: "Mutuo acuerdo", despido_justificado: "Despido justificado",
  despido_injustificado: "Despido injustificado", rescision_trabajador: "Rescisión (causa del patrón)", fallecimiento: "Fallecimiento",
};

/** Desglose del cálculo: secciones con concepto, operación, fundamento e importe. */
export function Desglose({ r, compacto = false }: { r: any; compacto?: boolean }) {
  if (!r) return null;
  return (
    <div className="space-y-4">
      {r.secciones.map((s: any) => (
        <section key={s.clave}>
          <div className="mb-1 flex items-baseline justify-between border-b border-crema-300 pb-1">
            <h3 className="text-xs font-bold uppercase tracking-wider text-turquesa-700">{s.titulo}</h3>
            <span className="text-sm font-bold text-marino">{mxn(s.subtotal)}</span>
          </div>
          <ul className="divide-y divide-crema-200">{s.conceptos.map((c: any) => (
            <li key={c.clave} className="py-1.5">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-semibold text-slate-800">{c.concepto}</span>
                <span className="whitespace-nowrap font-mono text-slate-800">{mxn(c.importe)}</span>
              </div>
              {!compacto && <p className="text-xs text-slate-500">{c.operacion}{c.fundamento !== "—" && <span className="text-slate-400"> · {c.fundamento}</span>}</p>}
            </li>))}</ul>
        </section>))}
      {!r.secciones.length && <p className="text-sm text-slate-500">No hay conceptos que pagar con estos datos.</p>}
    </div>
  );
}

export function Avisos({ avisos }: { avisos: string[] }) {
  if (!avisos?.length) return null;
  return <ul className="space-y-1 rounded-xl bg-amber-50 p-3 text-xs text-amber-900">{avisos.map((a) => <li key={a}>• {a}</li>)}</ul>;
}

export function Resumen({ r }: { r: any }) {
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
      <dt className="text-slate-500">Antigüedad</dt><dd className="text-right font-semibold text-slate-700">{r.antiguedad.anios} años ({r.antiguedad.dias} días)</dd>
      <dt className="text-slate-500">Salario diario</dt><dd className="text-right font-semibold text-slate-700">{mxn(r.salarios.diario)}</dd>
      <dt className="text-slate-500">Salario integrado</dt><dd className="text-right font-semibold text-slate-700">{mxn(r.salarios.integrado)} <span className="font-normal text-slate-400">(factor {r.salarios.factor})</span></dd>
      {r.salarios.minimo && <><dt className="text-slate-500">Salario mínimo {r.salarios.minimo_anio ?? "capturado"}{r.salarios.zona === "frontera" ? " (frontera)" : ""}</dt>
        <dd className="text-right font-semibold text-slate-700">{mxn(r.salarios.minimo)}</dd></>}
    </dl>
  );
}

/** Tarjeta para el asunto de la Agenda: exposición económica (suma de los cálculos de cada persona trabajadora). */
export function ExposicionAsunto({ asunto, puedeEditar }: { asunto: { id: number; materia?: string }; puedeEditar: boolean }) {
  const [e, setE] = useState<any>(null);
  useEffect(() => {
    if (!(leerSesion()?.modulos ?? ["nomina"]).includes("nomina")) return;
    api.get(`/liquidaciones/exposicion?asunto=${asunto.id}`).then(setE).catch(() => setE(null));
  }, [asunto.id]);
  if (!e || (!e.calculos.length && asunto.materia !== "laboral")) return null;
  return (
    <section className="tarjeta p-4">
      <div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-marino">Exposición económica</h2>
        {puedeEditar && <Link href={`/liquidaciones/nuevo?asunto=${asunto.id}`} className="text-sm font-semibold text-turquesa-700 underline">+ Calcular</Link>}</div>
      {e.calculos.length ? <>
        <ul className="mt-2 divide-y divide-crema-200 text-sm">{e.calculos.map((c: any) => (
          <li key={c.id} className="flex items-baseline justify-between gap-2 py-1.5">
            <Link href={`/liquidaciones/${c.id}`} className="font-semibold text-marino hover:underline">{c.trabajador}<span className="block text-xs font-normal text-slate-500">{CAUSA_CORTA[c.causa]}</span></Link>
            <span className="text-right font-mono">{mxn(c.total)}{c.propuesta && <span className="block text-xs text-slate-500">propuesta {mxn(c.propuesta)}</span>}</span></li>))}</ul>
        <div className="mt-2 flex items-baseline justify-between border-t border-crema-300 pt-2"><span className="text-xs font-bold uppercase tracking-wider text-slate-500">Total</span>
          <span className="text-xl font-black text-marino">{mxn(e.total)}</span></div>
        {(e.propuesta || e.autorizado) && <p className="text-right text-xs text-slate-500">{e.propuesta && <>Propuesta: {mxn(e.propuesta)}</>}{e.autorizado && <> · Autorizado: {mxn(e.autorizado)}</>}</p>}
      </> : <p className="mt-1 text-sm text-slate-500">Calcule el finiquito o la liquidación de cada persona y aquí verá cuánto está en juego en el asunto.</p>}
    </section>
  );
}

/** Tarjeta del asunto con accesos al Asistente IA y sus borradores recientes. */
export function AsistenteAsunto({ asunto }: { asunto: { id: number } }) {
  const [xs, setXs] = useState<any[] | null>(null);
  useEffect(() => {
    api.get(`/asistente/solicitudes?asunto=${asunto.id}`).then((r) => setXs(r.solicitudes)).catch(() => setXs(null));
  }, [asunto.id]);
  if (!xs) return null;
  return (
    <section className="tarjeta p-4">
      <div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-marino">Asistente IA</h2>
        <Link href={`/asistente?asunto=${asunto.id}`} className="text-sm font-semibold text-turquesa-700 underline">+ Redactar</Link></div>
      {xs.length ? <ul className="mt-2 space-y-1 text-sm">{xs.slice(0, 5).map((s) => (
        <li key={s.id}><Link href={`/asistente?asunto=${asunto.id}`} className="text-marino hover:underline">{s.titulo}</Link></li>))}</ul>
        : <p className="mt-1 text-sm text-slate-500">Pida un borrador de escrito o un resumen con los datos de este asunto.</p>}
    </section>
  );
}
