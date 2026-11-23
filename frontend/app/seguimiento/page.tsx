"use client";
import { useCallback, useEffect, useState } from "react";
import Logo from "@/components/Logo";

/** Seguimiento en línea de un trámite de escrituración. El enlace llega como /seguimiento#token: el fragmento no viaja
 *  al servidor; se quita de la barra y se manda en un encabezado. Solo muestra lo que la notaría decidió compartir. */
const CLAVE = "nomira_seguimiento";
const fecha = (iso?: string | null) => (iso ? new Date(iso.length === 10 ? iso + "T12:00" : iso).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" }) : "");
const fechaHora = (iso: string) => new Date(iso).toLocaleString("es-MX", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

async function llamar(ruta: string, token: string, init: RequestInit = {}) {
  const h = new Headers(init.headers);
  h.set("X-Enlace", token);
  const r = await fetch(`/api/seguimiento${ruta}`, { ...init, headers: h, cache: "no-store" });
  let d: any = null;
  try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error(typeof d?.detail === "string" ? d.detail : "No se pudo completar. Intente de nuevo.");
  return d;
}

const DOC: Record<string, [string, string]> = {
  pendiente: ["Pendiente de entregar", "bg-red-50 text-red-700"], rechazado: ["Hay que corregirlo", "bg-red-50 text-red-700"],
  recibido: ["Recibido, en revisión", "bg-amber-50 text-amber-800"], validado: ["Listo ✓", "bg-emerald-50 text-emerald-800"],
};

export default function Seguimiento() {
  const [token, setToken] = useState<string | null>(null);
  const [info, setInfo] = useState<any>(null);
  const [fatal, setFatal] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [subiendo, setSubiendo] = useState<number | null>(null);
  useEffect(() => {
    const h = window.location.hash.slice(1);
    if (h) { sessionStorage.setItem(CLAVE, h); history.replaceState(null, "", window.location.pathname); }
    const t = sessionStorage.getItem(CLAVE);
    if (!t) setFatal("Abra esta página desde el enlace que le compartió la notaría.");
    setToken(t);
  }, []);
  const cargar = useCallback(async () => {
    if (!token) return;
    try { setInfo(await llamar("/estado", token, { method: "POST" })); } catch (e: any) { setFatal(e.message); }
  }, [token]);
  useEffect(() => { cargar(); }, [cargar]);
  async function subir(d: any, archivo: File) {
    if (!token) return;
    setError(""); setOk(""); setSubiendo(d.id);
    try {
      const f = new FormData(); f.append("archivo", archivo); f.append("requisito_id", String(d.id));
      const r = await llamar("/documentos", token, { method: "POST", body: f });
      setOk(r.mensaje); await cargar();
    } catch (e: any) { setError(e.message); } finally { setSubiendo(null); }
  }
  const pendientes = info?.documentos.filter((d: any) => d.estado === "pendiente" || d.estado === "rechazado") || [];
  return (
    <main className="min-h-screen bg-crema">
      <header className="bg-marino-900 px-6 py-5"><div className="mx-auto flex max-w-2xl items-center justify-between gap-4">
        {info?.notaria.logo ? <img src={info.notaria.logo} alt={info.notaria.nombre} className="h-10 w-auto rounded bg-white p-1" /> : <Logo oscuro />}
        {info && <span className="text-right text-sm font-semibold text-white">{info.notaria.nombre}</span>}</div></header>
      <div className="h-1 bg-turquesa" />
      <div className="mx-auto max-w-2xl space-y-5 px-4 py-8">
        {fatal ? <section className="tarjeta p-8 text-center"><h1 className="text-2xl font-extrabold text-marino">No es posible abrir el seguimiento</h1><p className="mt-2 text-slate-600">{fatal}</p></section>
          : !info ? <p className="text-center text-slate-500" role="status">Cargando…</p> : <>
          <section className="tarjeta p-6">
            <p className="text-sm text-slate-500">Hola, {info.para}</p>
            <h1 className="text-2xl font-extrabold text-marino">{info.acto}</h1>
            <p className="text-slate-700">{info.titulo}</p>{info.inmueble && <p className="text-sm text-slate-500">📍 {info.inmueble}</p>}
            <p className="mt-1 font-mono text-xs text-slate-400">Folio {info.folio}</p>
            <div className="mt-4 flex items-center gap-3"><div className="h-3 flex-1 overflow-hidden rounded-full bg-crema-200"><div className="h-full rounded-full bg-turquesa" style={{ width: `${info.avance.porcentaje}%` }} /></div>
              <b className="text-marino">{info.avance.porcentaje}%</b></div>
            <p className="mt-1 text-sm text-slate-600">{info.estado === "concluido" ? "Trámite concluido. ¡Gracias por su confianza!" : <>Ahora: <b>{info.avance.actual}</b></>}</p>
            {info.mensaje && <p className="mt-3 rounded-xl bg-turquesa-50 p-3 text-sm text-marino">📣 {info.mensaje}</p>}
          </section>

          {info.cita_firma && <section className="tarjeta border-l-4 border-l-turquesa p-5">
            <p className="text-xs font-bold uppercase tracking-wide text-turquesa-700">Cita de firma</p>
            <p className="text-lg font-bold capitalize text-marino">{fechaHora(info.cita_firma)}</p>{info.cita_lugar && <p className="text-sm text-slate-600">{info.cita_lugar}</p>}
            <p className="mt-1 text-xs text-slate-500">Lleve su identificación oficial original.</p></section>}

          {info.documentos.length > 0 && <section className="tarjeta p-5">
            <h2 className="font-bold text-marino">Documentos {pendientes.length ? <span className="ml-1 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">{pendientes.length} pendiente(s)</span> : <span className="ml-1 text-xs text-emerald-700">✓ completos</span>}</h2>
            {info.puede_subir && pendientes.length > 0 && <p className="mb-2 text-sm text-slate-600">Puede subirlos aquí en PDF o foto (JPG, PNG). La notaría los revisará.</p>}
            {error && <p className="mb-2 rounded-lg bg-red-50 p-2 text-sm text-red-700" role="alert">{error}</p>}
            {ok && <p className="mb-2 rounded-lg bg-emerald-50 p-2 text-sm text-emerald-800" role="status">{ok}</p>}
            <ul className="divide-y divide-crema-200">{info.documentos.map((d: any) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <span><b className="text-marino">{d.nombre}</b><span className="block text-xs text-slate-500">{d.de}</span>
                  {d.nota && <span className="block text-xs font-semibold text-red-700">Corregir: {d.nota}</span>}</span>
                <span className="flex items-center gap-2"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${DOC[d.estado]?.[1]}`}>{DOC[d.estado]?.[0]}</span>
                  {info.puede_subir && ["pendiente", "rechazado", "recibido"].includes(d.estado) &&
                    <label className="btn-sec cursor-pointer px-3 py-1 text-xs">{subiendo === d.id ? "Subiendo…" : d.estado === "recibido" ? "Reemplazar" : "Subir"}
                      <input type="file" className="sr-only" accept="application/pdf,image/jpeg,image/png,image/webp" disabled={subiendo !== null}
                        onChange={(ev) => ev.target.files?.[0] && subir(d, ev.target.files[0])} aria-label={`Subir ${d.nombre}`} /></label>}</span>
              </li>))}</ul>
          </section>}

          <section className="tarjeta p-5">
            <h2 className="mb-3 font-bold text-marino">Avance</h2>
            <ol className="relative space-y-4 border-l-2 border-crema-300 pl-5">{info.etapas.map((s: any, i: number) => (
              <li key={i}><span className={`absolute -left-[9px] mt-0.5 flex h-4 w-4 items-center justify-center rounded-full text-[10px] ${s.estado === "hecho" ? "bg-emerald-500 text-white" : s.estado === "observado" ? "bg-amber-400 text-white" : s.estado === "en_proceso" ? "bg-turquesa" : "bg-crema-300"}`}>{s.estado === "hecho" ? "✓" : ""}</span>
                <p className={`text-sm ${s.estado === "hecho" ? "font-semibold text-marino" : s.estado === "pendiente" ? "text-slate-400" : "font-semibold text-marino"}`}>{s.nombre}
                  {s.estado === "en_proceso" && <span className="ml-2 rounded-full bg-turquesa-50 px-2 text-xs text-turquesa-700">en proceso</span>}
                  {s.estado === "observado" && <span className="ml-2 rounded-full bg-amber-100 px-2 text-xs text-amber-800">con observaciones</span>}</p>
                {s.fecha && <p className="text-xs text-slate-500">{fecha(s.fecha)}</p>}{s.nota && <p className="text-sm text-slate-700">{s.nota}</p>}</li>))}</ol>
            {(info.numero_escritura || info.folio_registro) && <p className="mt-4 rounded-lg bg-crema/70 p-3 text-xs text-slate-600">
              {info.numero_escritura && <>Escritura número <b>{info.numero_escritura}</b>. </>}{info.folio_registro && <>Entrada al Registro Público: <b>{info.folio_registro}</b>.</>}</p>}
          </section>
          <p className="text-center text-xs text-slate-500">{info.responsable && <>Le atiende: {info.responsable} · </>}{info.notaria.nombre}<br />Este enlace es personal: no lo comparta. Seguimiento con tecnología Nomira.</p>
        </>}
      </div>
    </main>
  );
}
