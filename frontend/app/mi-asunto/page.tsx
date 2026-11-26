"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ESTADO_ETAPA, fechaCorta, fechaHora, fechaLarga, LineaTiempo } from "@/components/connect";

/** Portal del cliente (Nomira Connect). El enlace llega como /mi-asunto#token: el fragmento no viaja al servidor;
 *  se quita de la barra y se manda en un encabezado. Muestra SOLO lo que el despacho decidió compartir. */
const CLAVE = "nomira_connect", CLAVE_SESION = "nomira_connect_sesion", CLAVE_ACC = "nomira_connect_acc";
const dinero = (v: string) => Number(v).toLocaleString("es-MX", { style: "currency", currency: "MXN" });

function guardado(k: string) { try { return sessionStorage.getItem(k); } catch { return null; } }
function guardar(k: string, v: string | null) { try { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch {} }

async function llamar(ruta: string, token: string, init: RequestInit = {}) {
  const h = new Headers(init.headers);
  h.set("X-Enlace", token);
  const s = guardado(CLAVE_SESION);
  if (s) h.set("X-Sesion", s);
  if (init.body) h.set("Content-Type", "application/json");
  const r = await fetch(`/api/mi-portal${ruta}`, { method: "POST", ...init, headers: h, cache: "no-store" });
  let d: any = null;
  try { d = await r.json(); } catch {}
  if (!r.ok) throw Object.assign(new Error(typeof d?.detail === "string" ? d.detail : "No se pudo completar. Intente de nuevo."), { estado: r.status });
  return d;
}

const MOTIVOS_BOTON: [string, string, string][] = [["seguimiento", "¿Cómo va mi asunto?", "💬"], ["llamada", "Quiero que me llamen", "📞"],
  ["cita", "Quiero una cita", "📅"], ["documentos", "Tengo documentos", "📄"], ["honorarios", "Duda de pagos", "💳"], ["otro", "Otra cosa", "✏️"]];

export default function MiAsunto() {
  const [token, setToken] = useState<string | null>(null);
  const [info, setInfo] = useState<any>(null);
  const [fatal, setFatal] = useState("");
  const [error, setError] = useState("");
  const [vista, setVista] = useState<"inicio" | "asunto" | "mensajes" | "pagos">("inicio");
  const [abierto, setAbierto] = useState<any>(null);
  const [acc, setAcc] = useState({ grande: false, contraste: false });
  const [logo, setLogo] = useState<string | null>(null);
  useEffect(() => {
    const h = window.location.hash.slice(1);
    if (h) { guardar(CLAVE, h); guardar(CLAVE_SESION, null); history.replaceState(null, "", window.location.pathname); }
    const t = guardado(CLAVE);
    if (!t) setFatal("Abra esta página desde el enlace que le compartió su despacho.");
    setToken(t);
    try { const a = localStorage.getItem(CLAVE_ACC); if (a) setAcc(JSON.parse(a)); } catch {}
  }, []);
  const cambiarAcc = (k: "grande" | "contraste") => setAcc((a) => { const n = { ...a, [k]: !a[k] }; try { localStorage.setItem(CLAVE_ACC, JSON.stringify(n)); } catch {} return n; });
  const cargar = useCallback(async () => {
    if (!token) return;
    try {
      const d = await llamar("/estado", token);
      setInfo(d); setError("");
      setAbierto((a: any) => a ? d.asuntos?.find((x: any) => x.id === a.id) ?? null : a);
    } catch (e: any) {
      if (e.estado === 401) { guardar(CLAVE_SESION, null); return cargar(); }
      setFatal(e.message);
    }
  }, [token]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (!token || !info?.logo) return;
    fetch("/api/mi-portal/logo", { headers: { "X-Enlace": token } }).then((r) => r.ok ? r.blob() : null).then((b) => b && setLogo(URL.createObjectURL(b))).catch(() => {});
  }, [token, info?.logo]);
  useEffect(() => { if (vista === "mensajes" && info?.mensajes_nuevos && token) llamar("/leido", token).then(cargar).catch(() => {}); }, [vista, info?.mensajes_nuevos, token, cargar]);

  const g = acc.grande;
  const raiz = `min-h-screen ${acc.contraste ? "cn-contraste bg-white" : "bg-crema"} ${g ? "text-[17px]" : ""}`;
  const Encabezado = (
    <header className={`sticky top-0 z-20 border-b ${acc.contraste ? "border-black bg-white" : "border-crema-300 bg-white/90 backdrop-blur"}`}>
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {logo ? <img src={logo} alt="" className="h-9 w-9 rounded-lg object-contain" /> : <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-marino text-sm font-bold text-white">{(info?.despacho || "·").slice(0, 1)}</span>}
          <span className="truncate font-bold text-marino">{info?.despacho || "Su despacho"}</span></div>
        <div className="flex shrink-0 gap-1.5" role="group" aria-label="Accesibilidad">
          <button onClick={() => cambiarAcc("grande")} aria-pressed={g} className={`rounded-lg border px-2.5 py-1.5 text-sm font-bold ${g ? "border-marino bg-marino text-white" : "border-crema-300 bg-white text-marino"}`} title="Letra más grande" aria-label="Letra más grande">A+</button>
          <button onClick={() => cambiarAcc("contraste")} aria-pressed={acc.contraste} className={`rounded-lg border px-2.5 py-1.5 text-sm font-bold ${acc.contraste ? "border-black bg-black text-white" : "border-crema-300 bg-white text-marino"}`} title="Alto contraste" aria-label="Alto contraste"><svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" /></svg></button>
        </div></div>
    </header>);
  const Pie = <footer className="mx-auto max-w-2xl px-4 pb-28 pt-8 text-center text-xs text-slate-500"><span>Powered by <b className="font-marca text-marino">nomira</b></span>
    <p className="mt-1">Solo usted ve esta página. No comparta su enlace.</p></footer>;

  if (fatal) return <div className={raiz}>{Encabezado}<main className="mx-auto max-w-md px-5 py-16 text-center"><p className="text-4xl">🔒</p><p className="mt-3 text-lg font-bold text-marino">{fatal}</p></main>{Pie}</div>;
  if (!info) return <div className={raiz}>{Encabezado}<p className="p-10 text-center text-slate-500">Cargando…</p></div>;
  if (!info.verificado) return <div className={raiz}>{Encabezado}<Verificar token={token!} info={info} onListo={cargar} grande={g} />{Pie}</div>;

  const pendientes = info.asuntos.filter((a: any) => a.accion_cliente || a.etapas.some((e: any) => e.estado === "atencion"));
  const audiencias = info.asuntos.flatMap((a: any) => a.audiencias.map((x: any) => ({ ...x, asunto: a.asunto }))).sort((a: any, b: any) => a.fecha.localeCompare(b.fecha));
  const nav: [typeof vista, string, string, number?][] = [["inicio", "Inicio", "🏠"], ["mensajes", "Mensajes", "💬", info.mensajes_nuevos], ...(info.pagos ? [["pagos", "Pagos", "💳"] as [typeof vista, string, string]] : [])];
  return (
    <div className={raiz}>
      {Encabezado}
      <main className="mx-auto max-w-2xl px-4 py-5">
        {error && <p className="mb-3 rounded-xl bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
        {vista === "inicio" && <>
          <h1 className={`font-marca font-extrabold text-marino ${g ? "text-3xl" : "text-2xl"}`}>Hola, {info.nombre}</h1>
          <p className="mt-1 text-slate-600">Aquí puede ver en qué va su asunto, sin tener que llamar.</p>
          {pendientes.map((a: any) => (
            <div key={a.id} className="mt-4 rounded-2xl border-2 border-amber-300 bg-amber-50 p-4" role="status">
              <p className="text-xs font-bold uppercase tracking-wider text-amber-800">⚠ Necesitamos algo de usted</p>
              <p className={`mt-1 font-semibold text-marino ${g ? "text-lg" : ""}`}>{a.accion_cliente || a.etapas.find((e: any) => e.estado === "atencion")?.nota || a.etapas.find((e: any) => e.estado === "atencion")?.nombre}</p>
              <p className="mt-1 text-xs text-slate-600">{a.asunto}</p></div>))}
          {!info.asuntos.length && <div className="mt-6 rounded-2xl bg-white p-6 text-center"><p className="font-bold text-marino">Su despacho aún no ha publicado el seguimiento de su asunto.</p>
            <p className="mt-1 text-sm text-slate-600">Mientras tanto, puede escribirles desde «Mensajes».</p></div>}
          <div className="mt-4 space-y-4">{info.asuntos.map((a: any) => <TarjetaAsunto key={a.id} a={a} g={g} onAbrir={() => { setAbierto(a); setVista("asunto"); window.scrollTo(0, 0); }} />)}</div>
          {info.preferencias?.avisos_activos && (info.preferencias.correo_disponible || info.preferencias.whatsapp_disponible) &&
            <PreferenciasAvisos p={info.preferencias} token={token!} g={g} onCambio={cargar} setError={setError} />}
          {audiencias.length > 0 && <section className="mt-5 rounded-2xl bg-white p-4"><h2 className={`font-bold text-marino ${g ? "text-xl" : ""}`}>📅 Próximas audiencias</h2>
            <ul className="mt-2 divide-y divide-crema-300">{audiencias.map((x: any, i: number) => (
              <li key={i} className="py-2"><p className="font-semibold text-marino">{fechaLarga(x.fecha).replace(/^./, (l: string) => l.toUpperCase())}{x.hora && ` · ${x.hora} h`}</p>
                <p className="text-sm text-slate-600">{x.titulo}{x.lugar && ` — ${x.lugar}`}</p><p className="text-xs text-slate-500">{x.asunto}</p></li>))}</ul>
            <p className="mt-2 text-xs text-slate-500">Su abogado le confirmará si necesita asistir.</p></section>}
        </>}
        {vista === "asunto" && abierto && <DetalleAsunto a={abierto} g={g} onVolver={() => setVista("inicio")} onPreguntar={() => setVista("mensajes")} />}
        {vista === "mensajes" && <Mensajes info={info} token={token!} g={g} asunto={abierto} onEnviado={cargar} setError={setError} />}
        {vista === "pagos" && info.pagos && <section>
          <h1 className={`font-marca font-extrabold text-marino ${g ? "text-3xl" : "text-2xl"}`}>Mis pagos</h1>
          <div className="mt-4 rounded-2xl bg-white p-5"><p className="text-sm text-slate-600">Saldo pendiente</p><p className="text-3xl font-extrabold text-marino">{dinero(info.pagos.saldo)}</p>
            {Number(info.pagos.vencido) > 0 && <p className="mt-1 text-sm font-semibold text-red-700">Vencido: {dinero(info.pagos.vencido)}</p>}</div>
          <ul className="mt-3 space-y-2">{info.pagos.pendientes.map((x: any, i: number) => (
            <li key={i} className="flex items-center justify-between rounded-2xl bg-white p-4"><span><span className="block font-semibold text-marino">{x.concepto}</span>
              <span className={`text-xs ${x.estado === "vencido" ? "font-semibold text-red-700" : "text-slate-500"}`}>{x.estado === "vencido" ? "Venció" : "Vence"} el {fechaCorta(x.vence)}</span></span>
              <span className="font-bold text-marino">{dinero(x.pendiente)}</span></li>))}</ul>
          {!info.pagos.pendientes.length && <p className="mt-3 rounded-2xl bg-emerald-50 p-4 text-emerald-800">✓ No tiene pagos pendientes.</p>}
          <p className="mt-3 text-xs text-slate-500">¿Dudas sobre un pago? Escríbale a su despacho en «Mensajes».</p></section>}
      </main>
      {Pie}
      <nav className={`fixed inset-x-0 bottom-0 z-20 border-t ${acc.contraste ? "border-black bg-white" : "border-crema-300 bg-white/95 backdrop-blur"}`} aria-label="Secciones">
        <div className="mx-auto flex max-w-2xl">{nav.map(([v, t, i, n]) => (
          <button key={v} onClick={() => { setVista(v); window.scrollTo(0, 0); }} aria-current={vista === v || (v === "inicio" && vista === "asunto") ? "page" : undefined}
            className={`relative flex flex-1 flex-col items-center gap-0.5 py-2.5 ${g ? "text-sm" : "text-xs"} font-semibold ${vista === v || (v === "inicio" && vista === "asunto") ? "text-turquesa-700" : "text-slate-500"}`}>
            <span className="text-xl" aria-hidden>{i}</span>{t}
            {!!n && <span className="absolute right-[calc(50%-22px)] top-1.5 rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">{n}</span>}</button>))}</div>
      </nav>
    </div>
  );
}

function PreferenciasAvisos({ p, token, g, onCambio, setError }: { p: any; token: string; g: boolean; onCambio: () => void; setError: (e: string) => void }) {
  const cambiar = async (k: "correo" | "whatsapp", v: boolean) => {
    try { await llamar("/preferencias", token, { body: JSON.stringify({ [k]: v }) }); onCambio(); } catch (e: any) { setError(e.message); }
  };
  const Fila = ({ k, t, d }: { k: "correo" | "whatsapp"; t: string; d: string }) => (
    <label className="flex items-center justify-between gap-3 py-2">
      <span><span className={`block font-semibold text-marino ${g ? "text-lg" : ""}`}>{t}</span><span className="text-xs text-slate-500">{d}</span></span>
      <button role="switch" aria-checked={p[k]} onClick={() => cambiar(k, !p[k])} className={`relative h-8 w-14 shrink-0 rounded-full transition ${p[k] ? "bg-turquesa" : "bg-slate-300"}`}>
        <span className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow transition ${p[k] ? "left-7" : "left-1"}`} /></button>
    </label>);
  return (
    <section className="mt-5 rounded-2xl bg-white p-4"><h2 className={`font-bold text-marino ${g ? "text-xl" : ""}`}>🔔 Avisos de su asunto</h2>
      <p className="text-sm text-slate-600">Le avisamos cuando haya una novedad. Usted elige cómo.</p>
      {p.correo_disponible && <Fila k="correo" t="Por correo" d={p.email} />}
      {p.whatsapp_disponible && <Fila k="whatsapp" t="Por WhatsApp" d={`Al número ${p.telefono}. Puede cancelarlo cuando quiera.`} />}
    </section>);
}

function TarjetaAsunto({ a, g, onAbrir }: { a: any; g: boolean; onAbrir: () => void }) {
  const e = a.etapa_actual;
  const est = ESTADO_ETAPA[e?.estado || "pendiente"];
  const hechas = a.etapas.filter((x: any) => x.estado === "completada").length;
  return (
    <button onClick={onAbrir} className="block w-full overflow-hidden rounded-3xl bg-white text-left shadow-sm ring-1 ring-crema-300 transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="bg-gradient-to-r from-marino to-marino-700 px-5 py-4 text-white">
        <p className={`font-bold ${g ? "text-lg" : ""}`}>{a.asunto}</p>
        <p className="text-xs text-white/70">{[a.numero && `Exp. ${a.numero}`, a.abogado && `Abogado: ${a.abogado}`].filter(Boolean).join(" · ")}</p></div>
      <div className="p-5">
        {a.estado !== "activo" && <p className="mb-2 inline-block rounded-full bg-violet-50 px-2 py-0.5 text-xs font-bold text-violet-800">{a.estado === "cerrado" ? "Asunto concluido" : "Suspendido temporalmente"}</p>}
        <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Etapa actual</p>
        <p className={`mt-0.5 font-extrabold text-marino ${g ? "text-2xl" : "text-xl"}`}>{e ? e.nombre : "—"}</p>
        {e && <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${est.chip}`}>{est.texto}</span>}
        <div className="mt-4 flex gap-1" aria-label={`${hechas} etapas completadas de ${a.etapas.length}`}>
          {a.etapas.map((x: any) => <span key={x.id} className={`h-1.5 flex-1 rounded-full ${x.estado === "completada" ? "bg-emerald-400" : ["actual", "atencion", "incidencia", "suspendida"].includes(x.estado) ? ESTADO_ETAPA[x.estado].punto.split(" ")[0] : "bg-slate-200"}`} />)}</div>
        <p className="mt-3 text-sm text-slate-600">{a.actualizado_en ? `Actualizado el ${fechaCorta(a.actualizado_en)}` : ""}<span className="float-right font-semibold text-turquesa-700">Ver detalle →</span></p>
      </div>
    </button>
  );
}

function DetalleAsunto({ a, g, onVolver, onPreguntar }: { a: any; g: boolean; onVolver: () => void; onPreguntar: () => void }) {
  const e = a.etapa_actual;
  return (
    <section>
      <button onClick={onVolver} className="mb-3 text-sm font-semibold text-turquesa-700">← Volver</button>
      <div className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-crema-300">
        <div className="bg-gradient-to-br from-marino via-marino to-marino-700 p-5 text-white">
          <p className="text-xs text-white/70">{a.especialidad}</p>
          <h1 className={`font-marca font-extrabold ${g ? "text-2xl" : "text-xl"}`}>{a.asunto}</h1>
          <dl className={`mt-3 grid grid-cols-2 gap-2 ${g ? "text-sm" : "text-xs"}`}>
            {[["Expediente", a.numero], ["Abogado", a.abogado], ["Inicio", fechaCorta(a.inicio)], ["Tribunal", a.tribunal]].filter(([, v]) => v).map(([k, v]) => (
              <div key={k as string}><dt className="text-white/60">{k}</dt><dd className="font-semibold">{v}</dd></div>))}</dl></div>
        {e && <div className={`border-b border-crema-300 p-5 ${ESTADO_ETAPA[e.estado].chip.split(" ")[0]}`}>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Su asunto está en</p>
          <p className={`font-extrabold text-marino ${g ? "text-2xl" : "text-xl"}`}>{e.nombre}</p>
          {e.explicacion && <p className="mt-1 leading-relaxed text-slate-700">{e.explicacion}</p>}
          {e.nota && <p className="mt-2 rounded-xl bg-white p-3 text-marino">💬 {e.nota}</p>}</div>}
        <div className="grid gap-px bg-crema-300 sm:grid-cols-2">
          <div className="bg-white p-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Último movimiento en el expediente</p>
            {a.ultimo_movimiento ? <><p className="mt-1 font-semibold text-marino">{fechaCorta(a.ultimo_movimiento.fecha)}</p><p className="text-sm text-slate-600">{a.ultimo_movimiento.texto}</p></>
              : <p className="mt-1 text-sm text-slate-500">Sin movimientos registrados todavía.</p>}</div>
          <div className="bg-white p-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Última revisión de su despacho</p>
            <p className="mt-1 text-sm text-marino">{a.ultima_revision ? fechaHora(a.ultima_revision) : "Sin registrar"}</p></div>
        </div>
      </div>
      {a.mensaje && <div className="mt-4 rounded-2xl bg-turquesa-50 p-4"><p className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Mensaje de su abogado</p><p className="mt-1 text-marino">{a.mensaje}</p></div>}
      {a.accion_cliente && <div className="mt-4 rounded-2xl border-2 border-amber-300 bg-amber-50 p-4"><p className="text-xs font-bold uppercase tracking-wider text-amber-800">⚠ Lo que necesitamos de usted</p><p className="mt-1 font-semibold text-marino">{a.accion_cliente}</p></div>}
      <div className="mt-4 rounded-3xl bg-white p-5"><h2 className={`mb-4 font-bold text-marino ${g ? "text-xl" : ""}`}>Las etapas de su asunto</h2><LineaTiempo etapas={a.etapas} grande={g} />
        <p className="mt-3 text-xs text-slate-500">Los tiempos de cada etapa dependen del tribunal o la autoridad. Su abogado le avisará de cada avance.</p></div>
      {a.historial.length > 0 && <div className="mt-4 rounded-3xl bg-white p-5"><h2 className={`mb-3 font-bold text-marino ${g ? "text-xl" : ""}`}>Novedades</h2>
        <ul className="space-y-3">{a.historial.map((h: any, i: number) => (
          <li key={i} className="border-l-2 border-turquesa/40 pl-3"><p className="text-xs text-slate-500">{fechaHora(h.fecha)}</p><p className="font-semibold text-marino">{h.titulo}</p>
            {h.detalle && <p className="text-sm text-slate-600">{h.detalle}</p>}</li>))}</ul></div>}
      <button onClick={onPreguntar} className="btn-turquesa mt-4 w-full py-4 text-base">💬 Preguntar a mi abogado sobre este asunto</button>
    </section>
  );
}

function Mensajes({ info, token, g, asunto, onEnviado, setError }: { info: any; token: string; g: boolean; asunto: any; onEnviado: () => void; setError: (e: string) => void }) {
  const [motivo, setMotivo] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);
  const fin = useRef<HTMLDivElement>(null);
  useEffect(() => { fin.current?.scrollIntoView({ block: "end" }); }, [info.mensajes.length]);
  const enviar = async () => {
    setEnviando(true); setError("");
    try {
      const r = await llamar("/mensajes", token, { body: JSON.stringify({ texto, motivo: motivo || "otro", asunto_id: asunto?.id ?? (info.asuntos.length === 1 ? info.asuntos[0].id : null) }) });
      setOk(r.mensaje); setTexto(""); setMotivo(null); onEnviado();
    } catch (e: any) { setError(e.message); }
    setEnviando(false);
  };
  return (
    <section>
      <h1 className={`font-marca font-extrabold text-marino ${g ? "text-3xl" : "text-2xl"}`}>Mensajes</h1>
      <p className="mt-1 text-slate-600">Escríbale a su despacho. Le responderán por aquí.</p>
      <div className="mt-4 space-y-3">
        {info.mensajes.map((x: any, i: number) => (
          <div key={i} className={`flex ${x.autor === "cliente" ? "justify-end" : ""}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 ${x.autor === "cliente" ? "bg-marino text-white" : "bg-white text-marino ring-1 ring-crema-300"}`}>
              {x.autor === "despacho" && <p className="text-xs font-bold text-turquesa-700">{x.por}</p>}
              <p className="whitespace-pre-wrap">{x.texto}</p>
              <p className={`mt-1 text-[11px] ${x.autor === "cliente" ? "text-white/60" : "text-slate-400"}`}>{fechaHora(x.fecha)}{x.autor === "cliente" && (x.atendido ? " · Atendido" : " · Recibido")}</p>
            </div></div>))}
        {!info.mensajes.length && <p className="rounded-2xl bg-white p-4 text-sm text-slate-500">Aún no hay mensajes.</p>}
        <div ref={fin} />
      </div>
      {ok && <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-emerald-800" role="status">✓ {ok}</p>}
      <div className="mt-5 rounded-3xl bg-white p-4 ring-1 ring-crema-300">
        <p className={`font-bold text-marino ${g ? "text-lg" : ""}`}>¿En qué le podemos ayudar?</p>
        <div className="mt-3 grid grid-cols-2 gap-2">{MOTIVOS_BOTON.map(([v, t, i]) => (
          <button key={v} onClick={() => setMotivo(v)} aria-pressed={motivo === v}
            className={`rounded-2xl border-2 p-3 text-left font-semibold transition ${g ? "text-base" : "text-sm"} ${motivo === v ? "border-turquesa bg-turquesa-50 text-marino" : "border-crema-300 text-slate-700"}`}>
            <span className="mr-1" aria-hidden>{i}</span>{t}</button>))}</div>
        {motivo && <>
          <label className="mt-3 block"><span className="sr-only">Su mensaje</span>
            <textarea className={`campo ${g ? "text-lg" : ""}`} rows={4} maxLength={2000} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Escriba aquí su mensaje" autoFocus /></label>
          {asunto && <p className="mt-1 text-xs text-slate-500">Sobre: {asunto.asunto}</p>}
          <button className="btn-turquesa mt-3 w-full py-4 text-base" disabled={enviando || texto.trim().length < 2} onClick={enviar}>{enviando ? "Enviando…" : "Enviar mensaje"}</button></>}
      </div>
    </section>
  );
}

function Verificar({ token, info, onListo, grande }: { token: string; info: any; onListo: () => void; grande: boolean }) {
  const [enviado, setEnviado] = useState<any>(null);
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const pedir = async () => { setCargando(true); setError(""); try { setEnviado(await llamar("/codigo", token)); } catch (e: any) { setError(e.message); } setCargando(false); };
  const verificar = async () => {
    setCargando(true); setError("");
    try { const r = await llamar("/verificar", token, { body: JSON.stringify({ codigo }) }); guardar(CLAVE_SESION, r.sesion); onListo(); } catch (e: any) { setError(e.message); }
    setCargando(false);
  };
  return (
    <main className="mx-auto max-w-md px-5 py-10">
      <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-crema-300">
        <p className="text-4xl" aria-hidden>👋</p>
        <h1 className={`mt-2 font-marca font-extrabold text-marino ${grande ? "text-3xl" : "text-2xl"}`}>Hola, {info.nombre}</h1>
        <p className="mt-2 text-slate-600">Para cuidar su información, le enviaremos un código de 6 números a su correo <b>{info.email}</b>.</p>
        {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
        {!enviado ? <button className="btn-turquesa mt-5 w-full py-4 text-base" disabled={cargando} onClick={pedir}>{cargando ? "Enviando…" : "Enviarme el código"}</button> : <>
          <p className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">Le enviamos el código a {enviado.email}. Vence en {enviado.minutos} minutos.</p>
          <label className="mt-4 block"><span className="etiqueta">Código</span>
            <input className="campo text-center font-mono text-3xl tracking-[0.4em]" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={codigo}
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} autoFocus /></label>
          <button className="btn-turquesa mt-4 w-full py-4 text-base" disabled={cargando || codigo.length !== 6} onClick={verificar}>Entrar</button>
          <button className="mt-3 w-full text-sm font-semibold text-turquesa-700" onClick={pedir} disabled={cargando}>Enviarme otro código</button></>}
      </div>
    </main>
  );
}
