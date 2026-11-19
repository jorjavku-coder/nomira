"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Logo from "@/components/Logo";

/** Página pública para que el cliente de un despacho SUBA documentos. No muestra nada del expediente.
 *  El enlace llega como /subir#token: el fragmento nunca viaja al servidor; aquí se lee, se quita de la
 *  barra de direcciones y se manda en un encabezado. */
const CLAVE = "nomira_subida", CLAVE_SESION = "nomira_subida_sesion";
const fechaLarga = (iso: string) => new Date(iso).toLocaleString("es-MX", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
type Archivo = { file: File; como: string };

async function llamar(ruta: string, token: string, init: RequestInit = {}) {
  const h = new Headers(init.headers);
  h.set("X-Enlace", token);
  const s = sessionStorage.getItem(CLAVE_SESION);
  if (s) h.set("X-Sesion", s);
  if (init.body && !(init.body instanceof FormData)) h.set("Content-Type", "application/json");
  const r = await fetch(`/api/subida${ruta}`, { ...init, headers: h, cache: "no-store" });
  let datos: any = null;
  try { datos = await r.json(); } catch {}
  if (!r.ok) throw Object.assign(new Error(typeof datos?.detail === "string" ? datos.detail : "No se pudo completar la acción. Intente de nuevo."), { estado: r.status });
  return datos;
}

export default function Subir() {
  const [token, setToken] = useState<string | null>(null);
  const [info, setInfo] = useState<any>(null);
  const [fatal, setFatal] = useState("");
  const [error, setError] = useState("");
  const [codigoEnviado, setCodigoEnviado] = useState<any>(null);
  const [codigo, setCodigo] = useState("");
  const [archivos, setArchivos] = useState<Archivo[]>([]);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<any>(null);
  const entrada = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const deHash = window.location.hash.slice(1);
    if (deHash) {
      if (sessionStorage.getItem(CLAVE) !== deHash) sessionStorage.removeItem(CLAVE_SESION);
      sessionStorage.setItem(CLAVE, deHash);
      history.replaceState(null, "", window.location.pathname);  // el enlace no queda a la vista ni en el historial
    }
    const t = sessionStorage.getItem(CLAVE);
    if (!t) setFatal("Abra esta página desde el enlace que le envió su despacho por correo.");
    setToken(t);
  }, []);

  const cargar = useCallback(async () => {
    if (!token) return;
    try { setInfo(await llamar("/estado", token, { method: "POST" })); }
    catch (e: any) { setFatal(e.message); }
  }, [token]);
  useEffect(() => { cargar(); }, [cargar]);

  async function pedirCodigo() {
    setError("");
    try { setCodigoEnviado(await llamar("/codigo", token!, { method: "POST" })); } catch (e: any) { setError(e.message); }
  }
  async function verificar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      const r = await llamar("/verificar", token!, { method: "POST", body: JSON.stringify({ codigo }) });
      sessionStorage.setItem(CLAVE_SESION, r.sesion);
      setCodigo(""); setCodigoEnviado(null); cargar();
    } catch (err: any) { setError(err.message); }
  }
  function agregar(lista: FileList | null) {
    if (!lista) return;
    const pendientes = info.estado_documentos.find((x: any) => !x.enviados)?.documento || "";
    setArchivos([...archivos, ...Array.from(lista).map((file) => ({ file, como: info.documentos.length === 1 ? info.documentos[0] : pendientes }))]
      .slice(0, Math.min(info.max_por_envio, info.archivos_restantes)));
    if (entrada.current) entrada.current.value = "";
  }
  async function enviar() {
    setError(""); setEnviando(true);
    const fd = new FormData();
    archivos.forEach((a) => { fd.append("archivos", a.file); fd.append("solicitado_como", a.como); });
    try {
      const r = await llamar("/archivos", token!, { method: "POST", body: fd });
      setResultado(r); setArchivos([]); cargar();
    } catch (e: any) {
      if (e.estado === 401) sessionStorage.removeItem(CLAVE_SESION);
      setError(e.message); if (e.estado === 401) cargar();
    }
    setEnviando(false);
  }

  const grande = info ? archivos.find((a) => a.file.size > info.max_mb * 1048576) : null;
  return (
    <main className="min-h-screen bg-crema">
      <header className="bg-marino-900 px-6 py-5"><div className="mx-auto max-w-2xl"><Logo oscuro /></div></header>
      <div className="h-1 bg-turquesa" />
      <div className="mx-auto max-w-2xl px-4 py-8">
        {fatal ? (
          <section className="tarjeta p-8 text-center">
            <h1 className="text-2xl font-extrabold text-marino">No es posible enviar documentos</h1>
            <p className="mt-2 text-slate-600">{fatal}</p>
          </section>
        ) : !info ? (
          <p className="text-center text-slate-500" role="status">Cargando…</p>
        ) : (
          <div className="space-y-5">
            <section className="tarjeta p-6">
              <p className="text-sm font-semibold text-turquesa-700">{info.despacho}</p>
              <h1 className="mt-1 text-2xl font-extrabold text-marino">Envío seguro de documentos</h1>
              <p className="mt-2 text-slate-600">{info.solicita ? `${info.solicita} le` : "Su despacho le"} pide los siguientes documentos. Esta página solo sirve para enviarlos: no muestra información de su asunto.</p>
              {info.mensaje && <p className="mt-4 whitespace-pre-line rounded-xl border-l-4 border-turquesa bg-crema/70 p-4 text-slate-700">{info.mensaje}</p>}
              {info.documentos.length > 0 && (
                <ul className="mt-4 space-y-1.5">
                  {(info.verificado ? info.estado_documentos : info.documentos.map((d: string) => ({ documento: d }))).map((x: any) => (
                    <li key={x.documento} className="flex items-center justify-between gap-2 rounded-lg bg-white px-3 py-2 ring-1 ring-crema-300">
                      <span>{x.documento}</span>
                      {x.enviados !== undefined && (x.enviados ? <span className="text-sm font-semibold text-emerald-700">✓ Enviado{x.enviados > 1 ? ` (${x.enviados})` : ""}</span>
                        : <span className="text-sm text-slate-500">Pendiente</span>)}
                    </li>))}
                </ul>
              )}
              <p className="mt-4 text-xs text-slate-500">Enlace válido hasta el {fechaLarga(info.expira_en)}</p>
            </section>

            {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

            {!info.verificado ? (
              <section className="tarjeta p-6">
                <h2 className="text-lg font-bold text-marino">1. Confirme que es usted</h2>
                <p className="mt-1 text-sm text-slate-600">Le enviaremos un código de 6 dígitos a <b>{info.email}</b>.</p>
                {!codigoEnviado ? (
                  <button className="btn-primario mt-4" onClick={pedirCodigo}>Enviarme el código</button>
                ) : (
                  <form onSubmit={verificar} className="mt-4 flex flex-wrap items-end gap-3">
                    <label className="block"><span className="etiqueta">Código (vence en {codigoEnviado.minutos} minutos)</span>
                      <input className="campo w-44 text-center font-mono text-2xl tracking-[0.4em]" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required autoFocus
                        value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} /></label>
                    <button className="btn-primario">Verificar</button>
                    <button type="button" className="text-sm font-semibold text-turquesa-700 hover:underline" onClick={pedirCodigo}>Enviar otro código</button>
                  </form>
                )}
              </section>
            ) : info.estado !== "activa" ? (
              <section className="tarjeta p-6"><p className="text-slate-700">Ya se recibió el máximo de archivos para este enlace. Si necesita enviar más, pídale a su despacho un enlace nuevo.</p></section>
            ) : (
              <section className="tarjeta p-6">
                <h2 className="text-lg font-bold text-marino">{info.requiere_codigo ? "2. " : ""}Elija sus archivos</h2>
                <p className="mt-1 text-sm text-slate-600">PDF o fotografías (JPG, PNG, WebP), hasta {info.max_mb} MB cada uno. Puede enviar {info.archivos_restantes} archivo(s) más, {info.max_por_envio} a la vez.</p>
                <div className="mt-4 rounded-xl border-2 border-dashed border-crema-300 bg-white p-6 text-center" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); agregar(e.dataTransfer.files); }}>
                  <input ref={entrada} type="file" multiple className="hidden" accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" onChange={(e) => agregar(e.target.files)} />
                  <button className="btn-turquesa" onClick={() => entrada.current?.click()}>Elegir archivos</button>
                  <p className="mt-2 text-xs text-slate-500">o arrástrelos aquí</p>
                </div>
                {archivos.length > 0 && (
                  <ul className="mt-4 space-y-2">
                    {archivos.map((a, i) => (
                      <li key={i} className="flex flex-wrap items-center gap-2 rounded-xl bg-crema/60 p-3 text-sm">
                        <span className="min-w-0 grow truncate font-semibold">{a.file.name} <span className="font-normal text-slate-500">· {(a.file.size / 1048576).toFixed(1)} MB</span></span>
                        {info.documentos.length > 0 && (
                          <select className="campo w-auto py-1 text-sm" value={a.como} aria-label={`Qué documento es ${a.file.name}`}
                            onChange={(e) => setArchivos(archivos.map((x, j) => (j === i ? { ...x, como: e.target.value } : x)))}>
                            <option value="">Otro documento</option>
                            {info.documentos.map((d: string) => <option key={d} value={d}>{d}</option>)}
                          </select>)}
                        <button className="text-slate-500 hover:text-red-700" aria-label={`Quitar ${a.file.name}`} onClick={() => setArchivos(archivos.filter((_, j) => j !== i))}>✕</button>
                      </li>))}
                  </ul>
                )}
                {grande && <p className="mt-2 text-sm text-red-700">«{grande.file.name}» supera {info.max_mb} MB.</p>}
                <button className="btn-primario mt-4 w-full" disabled={!archivos.length || enviando || !!grande} onClick={enviar}>
                  {enviando ? "Enviando…" : `Enviar ${archivos.length || ""} archivo(s)`}</button>
              </section>
            )}

            {resultado && (
              <section className="tarjeta border-emerald-300 p-6" role="status">
                <h2 className="text-lg font-bold text-emerald-800">{resultado.recibidos ? `✓ Recibimos ${resultado.recibidos} archivo(s)` : "No se recibió ningún archivo"}</h2>
                <ul className="mt-2 space-y-1 text-sm">
                  {resultado.resultados.map((x: any, i: number) => <li key={i} className={x.aceptado ? "text-slate-700" : "text-red-700"}>{x.aceptado ? "✓" : "✕"} {x.nombre}{!x.aceptado && `: ${x.motivo}`}</li>)}
                </ul>
                {resultado.recibidos > 0 && <p className="mt-3 text-sm text-slate-600">Su despacho ya fue avisado y los revisará. Puede cerrar esta página o enviar más archivos.</p>}
              </section>
            )}

            {info.mis_envios?.length > 0 && (
              <section className="tarjeta p-6">
                <h2 className="font-bold text-marino">Lo que usted ha enviado</h2>
                <ul className="mt-2 divide-y divide-crema-300 text-sm">
                  {info.mis_envios.map((x: any, i: number) => (
                    <li key={i} className="py-2"><b>{x.nombre}</b>{x.solicitado_como && <span className="text-slate-500"> · {x.solicitado_como}</span>}
                      <div className="text-xs text-slate-500">{fechaLarga(x.fecha)} · {x.estado}</div></li>))}
                </ul>
              </section>
            )}
          </div>
        )}
        <p className="mt-8 text-center text-xs text-slate-400">Enlace seguro de Nomira. Nadie de su despacho le pedirá contraseñas por este medio.</p>
      </div>
    </main>
  );
}
