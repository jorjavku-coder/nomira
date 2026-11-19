"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AforeShell } from "@/components/afore";
import { Aviso } from "@/components/ui";
import { api, fecha } from "@/lib/api";

/** «¿Qué requiere atención ahora?»: cada indicador abre la lista o el caso correspondiente. */
export default function ResumenAfore() {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get("/afore/resumen").then(setR).catch((e) => setError(e.message)); }, []);
  const Grupo = ({ titulo, explicacion, items, ver, render }: { titulo: string; explicacion: string; items: any[]; ver: string; render: (x: any) => React.ReactNode }) => (
    <section className={`tarjeta overflow-hidden ${items.length ? "" : "opacity-70"}`}>
      <div className="flex items-center justify-between gap-2 border-b border-crema-300 bg-crema/40 px-5 py-3">
        <div><h2 className="font-semibold text-marino">{titulo} <span className={`ml-1 rounded-full px-2 text-xs ${items.length ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-500"}`}>{items.length}</span></h2>
          <p className="text-xs text-slate-500">{explicacion}</p></div>
        {items.length > 0 && <Link className="whitespace-nowrap text-sm font-semibold text-turquesa-700 hover:underline" href={ver}>Ver lista →</Link>}
      </div>
      <ul className="divide-y divide-crema-200">
        {items.length === 0 && <li className="px-5 py-3 text-sm text-slate-400">Nada por ahora.</li>}
        {items.slice(0, 5).map((x, i) => (
          <li key={i}><Link href={`/afore/casos/${x.caso_id}`} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5 text-sm hover:bg-crema/50">
            <span><b className="text-marino">{x.cliente}</b> <span className="text-slate-500">· {x.tipo}</span></span>
            <span className="text-xs text-slate-600">{render(x)}</span></Link></li>))}
      </ul>
    </section>
  );
  return (
    <AforeShell>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">¿Qué requiere atención ahora?</h1>
          <p className="mt-1 text-sm text-slate-500">Lo pendiente de todos sus casos AFORE abiertos, ordenado por lo que suele urgir más.</p></div>
        <Link href="/afore/casos/nuevo" className="btn-turquesa">+ Nuevo caso</Link>
      </div>
      <Aviso>{error}</Aviso>
      {!r && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {r && (
        <div className="space-y-5">
          {(r.mensajes.por_aprobar + r.mensajes.con_error + r.mensajes.por_asignar) > 0 && (
            <section className="tarjeta flex flex-wrap items-center gap-3 border-amber-300 bg-amber-50/50 p-4 text-sm">
              <b className="text-marino">Mensajes:</b>
              {r.mensajes.por_aprobar > 0 && <Link className="font-semibold text-amber-800 hover:underline" href="/afore/mensajes?bandeja=por_aprobar">{r.mensajes.por_aprobar} esperan su aprobación</Link>}
              {r.mensajes.con_error > 0 && <Link className="font-semibold text-red-700 hover:underline" href="/afore/mensajes?bandeja=errores">{r.mensajes.con_error} con error</Link>}
              {r.mensajes.por_asignar > 0 && <Link className="font-semibold text-violet-800 hover:underline" href="/afore/mensajes?bandeja=por_asignar">{r.mensajes.por_asignar} recibidos por asignar</Link>}
            </section>
          )}
          <div className="grid gap-5 xl:grid-cols-2">
            <Grupo titulo="Seguimientos vencidos o próximos" explicacion="Fechas de los próximos 3 días o ya pasadas." items={r.seguimientos} ver="/afore/casos?filtro=abiertos"
              render={(x) => <span className={x.vencido ? "font-semibold text-red-700" : "text-amber-700"}>{x.descripcion} · {x.vencido ? "venció" : "vence"} el {fecha(x.fecha)}</span>} />
            <Grupo titulo="Respuestas y documentos recién recibidos" explicacion="Respuestas de los últimos 7 días y documentos por revisar." items={[...r.respuestas_recientes, ...r.documentos_por_revisar]} ver="/afore/casos?filtro=abiertos"
              render={(x) => x.documento ? `Documento del cliente: ${x.documento}` : x.n ? `${x.n} documento(s) por revisar` : `Respuesta ${x.institucion ? `de ${x.institucion}` : ""} · ${fecha(x.fecha)}`} />
            <Grupo titulo="Gestiones que esperan respuesta" explicacion="Solicitudes o quejas sin respuesta registrada." items={r.esperando_respuesta} ver="/afore/casos?filtro=esperando"
              render={(x) => `${x.dias} día(s) esperando`} />
            <Grupo titulo="Clientes con documentos pendientes" explicacion="Documentos pedidos al cliente o que requieren corrección." items={r.documentos_pendientes} ver="/afore/casos?filtro=docs_pendientes"
              render={(x) => `${x.n} pendiente(s)`} />
            <Grupo titulo="Casos sin siguiente actividad" explicacion="Casos en atención sin una próxima tarea definida." items={r.sin_siguiente_actividad} ver="/afore/casos?filtro=sin_siguiente"
              render={() => "Definir siguiente paso"} />
            <Grupo titulo="Casos guardados como borrador" explicacion="Altas que no se terminaron." items={r.borradores} ver="/afore/casos?filtro=borradores" render={() => "Continuar alta"} />
          </div>
        </div>
      )}
    </AforeShell>
  );
}
