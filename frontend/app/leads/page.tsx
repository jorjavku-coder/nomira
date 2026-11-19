"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AltaRapida, FilaProspecto, LeadsShell } from "@/components/leads";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

const ORDEN: [string, string][] = [
  ["nuevos", "Aún nadie les ha respondido."], ["responder", "Escribieron y esperan respuesta."], ["citas", "Consultas de los próximos 14 días."],
  ["seguimientos", "Pasos de hoy o ya vencidos."], ["sin_actividad", "Sin próximo paso o sin movimiento reciente."], ["contratados", "Clientes de los últimos 90 días."],
];

/** Bandeja: qué requiere atención ahora. Cada indicador abre su lista. */
export default function BandejaLeads() {
  const [b, setB] = useState<any>(null);
  const [error, setError] = useState("");
  const [alta, setAlta] = useState(false);
  const [puede, setPuede] = useState(false);
  useEffect(() => {
    api.get("/leads/bandeja").then(setB).catch((e) => setError(e.message));
    api.get("/leads/catalogos").then((c) => setPuede(c.puede_editar)).catch(() => {});
  }, []);
  const vacio = b && Object.values(b.grupos).every((g: any) => g.total === 0) && !b.borradores;
  return (
    <LeadsShell>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">¿A quién hay que atender?</h1>
          <p className="mt-1 text-sm text-slate-500">Sus prospectos ordenados por lo que necesitan ahora.</p></div>
        {puede && <button className="btn-turquesa text-base" onClick={() => setAlta(true)}>+ Agregar prospecto</button>}
      </div>
      <Aviso>{error}</Aviso>
      {!b && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {b && (b.por_asignar > 0 || b.borradores > 0) && (
        <section className="tarjeta mb-5 flex flex-wrap items-center gap-4 border-amber-300 bg-amber-50/50 p-4 text-sm">
          {b.por_asignar > 0 && <Link className="font-semibold text-violet-800 hover:underline" href="/leads/prospectos?vista=por_asignar">{b.por_asignar} mensaje(s) de WhatsApp por asignar</Link>}
          {b.borradores > 0 && <Link className="font-semibold text-amber-800 hover:underline" href="/leads/prospectos?vista=borradores">{b.borradores} alta(s) guardada(s) como borrador</Link>}
        </section>
      )}
      {vacio && (
        <section className="tarjeta mb-5 p-6 text-sm">
          <h2 className="text-lg font-bold text-marino">Empiece aquí</h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-slate-700">
            <li>Registre a la próxima persona que pida informes con <b>«Agregar prospecto»</b> (menos de un minuto).</li>
            <li>En <Link className="font-semibold text-turquesa-700 underline" href="/leads/campanas">Campañas y fuentes</Link> copie su enlace de contacto para su sitio web, redes sociales o correos: quien lo llene aparece aquí solo.</li>
            <li>Si tiene WhatsApp Business Platform o anuncios de Facebook e Instagram, conéctelos en <Link className="font-semibold text-turquesa-700 underline" href="/leads/configuracion">Configuración</Link>.</li>
          </ol>
        </section>
      )}
      {b && (
        <div className="grid gap-5 xl:grid-cols-2">
          {ORDEN.map(([k, explicacion]) => {
            const g = b.grupos[k];
            return (
              <section key={k} className={`tarjeta overflow-hidden ${g.total ? "" : "opacity-70"}`}>
                <Link href={`/leads/prospectos?vista=${k}`} className="flex items-center justify-between gap-2 border-b border-crema-300 bg-crema/40 px-4 py-3 hover:bg-crema">
                  <div><h2 className="font-semibold text-marino">{g.titulo} <span className={`ml-1 rounded-full px-2 text-xs ${g.total ? (k === "contratados" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800") : "bg-slate-100 text-slate-500"}`}>{g.total}</span></h2>
                    <p className="text-xs text-slate-500">{explicacion}</p></div>
                  <span className="whitespace-nowrap text-sm font-semibold text-turquesa-700">Ver lista →</span>
                </Link>
                <div className="divide-y divide-crema-200">
                  {g.filas.length === 0 && <p className="px-4 py-3 text-sm text-slate-400">Nada por ahora.</p>}
                  {g.filas.map((f: any) => <FilaProspecto key={f.id} f={f} />)}
                </div>
              </section>
            );
          })}
        </div>
      )}
      {alta && <AltaRapida onCerrar={() => setAlta(false)} />}
    </LeadsShell>
  );
}
