"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import ShellPlataforma from "@/components/plataforma";
import { Aviso, Chip } from "@/components/ui";
import { fecha, fechaHora } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

const TIPOS: Record<string, string> = { bienvenida: "Bienvenida", recordatorio_vencimiento: "Recordatorio de vencimiento", prueba: "Prueba" };

export default function Correos() {
  const [d, setD] = useState<any>(null);
  const [vista, setVista] = useState<"bienvenida" | "recordatorio">("bienvenida");
  const [html, setHtml] = useState("");
  const [destino, setDestino] = useState("");
  const [msj, setMsj] = useState<{ tipo: "ok" | "error"; t: string } | null>(null);
  const [resultados, setResultados] = useState<any[] | null>(null);
  const [ocupado, setOcupado] = useState("");
  const cargar = useCallback(() => apiP.get("/correos").then(setD).catch((e) => setMsj({ tipo: "error", t: e.message })), []);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { apiP.texto(`/correos/vista-previa/${vista}`).then(setHtml).catch(() => setHtml("")); }, [vista]);

  async function prueba(e: React.FormEvent) {
    e.preventDefault(); setMsj(null); setOcupado("prueba");
    try {
      const r = await apiP.post("/correos/prueba", { destinatario: destino });
      setMsj(r.enviado ? { tipo: "ok", t: `Listo: revise la bandeja de ${destino} (y la carpeta de spam la primera vez).` } : { tipo: "error", t: r.error });
      cargar();
    } catch (err: any) { setMsj({ tipo: "error", t: err.message }); }
    setOcupado("");
  }
  async function ejecutar() {
    setMsj(null); setOcupado("ejecutar");
    try { setResultados(await apiP.post("/recordatorios/ejecutar")); cargar(); } catch (err: any) { setMsj({ tipo: "error", t: err.message }); }
    setOcupado("");
  }
  const c = d?.config;
  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Correos</h1>
      <p className="mb-5 mt-1 text-sm text-slate-500">Bienvenida automática a cada cliente nuevo y recordatorio {c ? c.recordatorio_dias : 7} días antes de que venza su plan.</p>

      {c && (c.configurado
        ? <Aviso tipo="ok">Envío activo con <b>{c.proveedor === "resend" ? "Resend" : `SMTP (${c.servidor})`}</b>, como <b>{c.remitente}</b>. Los enlaces apuntan a {c.url_publica}.</Aviso>
        : <Aviso tipo="alerta"><b>El envío de correos todavía no está configurado.</b> Mientras tanto no sale ningún correo: al crear un cliente verá sus datos para enviarlos usted. Se activa con las variables <code>CORREO_PROVEEDOR</code> y las de su proveedor en Render.</Aviso>)}
      <div className="mt-3"><Aviso tipo={msj?.tipo === "ok" ? "ok" : "error"}>{msj?.t}</Aviso></div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_24rem]">
        <section className="tarjeta overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-5 py-3">
            <h2 className="font-semibold text-marino">Plantillas</h2>
            <div className="flex gap-1" role="tablist">
              {([["bienvenida", "Bienvenida"], ["recordatorio", "Recordatorio"]] as const).map(([v, t]) => (
                <button key={v} role="tab" aria-selected={vista === v} onClick={() => setVista(v)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${vista === v ? "bg-marino text-white" : "text-slate-600 hover:bg-crema"}`}>{t}</button>))}
            </div>
          </div>
          <iframe title={`Vista previa del correo de ${vista}`} srcDoc={html} sandbox="" className="h-[44rem] w-full bg-crema" />
          <p className="border-t border-crema-300 px-5 py-2 text-xs text-slate-500">Vista previa con datos de ejemplo. Cada correo lleva también una versión de solo texto.</p>
        </section>

        <div className="space-y-6">
          <section className="tarjeta p-5">
            <h2 className="font-semibold text-marino">Enviarme una prueba</h2>
            <p className="mt-1 text-sm text-slate-500">Manda la plantilla de bienvenida (con datos de ejemplo) para revisar cómo llega.</p>
            <form onSubmit={prueba} className="mt-3 space-y-2">
              <input className="campo" type="email" required placeholder="su-correo@ejemplo.com" value={destino} onChange={(e) => setDestino(e.target.value)} aria-label="Correo para la prueba" />
              <button className="btn-primario w-full" disabled={!c?.configurado || ocupado === "prueba"}>{ocupado === "prueba" ? "Enviando…" : "Enviar prueba"}</button>
            </form>
          </section>

          <section className="tarjeta p-5">
            <h2 className="font-semibold text-marino">Recordatorios por enviar</h2>
            <p className="mt-1 text-sm text-slate-500">Se revisan solos cada hora. Van a los administradores de cada cliente, una sola vez por periodo.</p>
            <ul className="mt-3 divide-y divide-crema-300 text-sm">
              {d?.pendientes.length === 0 && <li className="py-2 text-slate-500">Ninguno por ahora.</li>}
              {d?.pendientes.map((p: any) => (
                <li key={p.organizacion_id} className="py-2">
                  <Link href={`/plataforma/clientes/${p.organizacion_id}#suscripcion`} className="font-semibold text-marino hover:underline">{p.cliente}</Link>
                  <div className="text-xs text-slate-500">Vence el {fecha(p.vence)} ({p.dias === 0 ? "hoy" : p.dias === 1 ? "mañana" : `en ${p.dias} días`}) · {p.destinatarios.join(", ") || "sin administradores activos"}</div>
                </li>))}
            </ul>
            <button className="btn-sec mt-3 w-full" disabled={!c?.configurado || ocupado === "ejecutar" || !d?.pendientes.length} onClick={ejecutar}>
              {ocupado === "ejecutar" ? "Enviando…" : "Enviar ahora"}</button>
            {resultados && <ul className="mt-3 space-y-1 text-xs">{resultados.length === 0 ? <li className="text-slate-500">No había nada por enviar.</li>
              : resultados.map((r, i) => <li key={i} className={r.estado === "enviado" ? "text-emerald-700" : "text-red-700"}>{r.estado === "enviado" ? "✓" : "✕"} {r.cliente}: {r.detalle}</li>)}</ul>}
          </section>
        </div>
      </div>

      <section className="tarjeta mt-6 overflow-x-auto">
        <div className="border-b border-crema-300 px-5 py-3"><h2 className="font-semibold text-marino">Historial</h2></div>
        <table className="tabla">
          <thead><tr><th>Fecha</th><th>Tipo</th><th>Cliente</th><th>Para</th><th>Estado</th></tr></thead>
          <tbody>
            {d?.historial.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-slate-500">Todavía no se ha enviado ningún correo.</td></tr>}
            {d?.historial.map((h: any) => (
              <tr key={h.id}>
                <td className="whitespace-nowrap">{fechaHora(h.fecha)}</td>
                <td>{TIPOS[h.tipo] || h.tipo}</td>
                <td>{h.organizacion_id ? <Link className="text-marino hover:underline" href={`/plataforma/clientes/${h.organizacion_id}`}>{h.cliente}</Link> : <span className="text-slate-400">—</span>}</td>
                <td className="max-w-[18rem] truncate text-sm" title={h.destinatarios}>{h.destinatarios}</td>
                <td>{h.estado === "enviado" ? <Chip estado="activo" texto="Enviado" /> : h.estado === "error"
                  ? <span title={h.error || ""}><Chip estado="error" texto="Falló" /><div className="mt-1 max-w-[22rem] text-xs text-red-700">{h.error}</div></span>
                  : <Chip estado="pendiente" texto="Enviando" />}</td>
              </tr>))}
          </tbody>
        </table>
      </section>
    </ShellPlataforma>
  );
}
