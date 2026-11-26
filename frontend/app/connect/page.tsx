"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { EditorEtapas, ESTADO_ETAPA, fechaHora } from "@/components/connect";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

/** Nomira Connect — panel del despacho: asuntos con seguimiento, mensajes de clientes y plantillas de etapas. */
function Connect() {
  const sp = useSearchParams();
  const router = useRouter();
  const [tab, setTab] = useState<"asuntos" | "mensajes" | "plantillas">(sp.get("cliente") || sp.get("tab") === "mensajes" ? "mensajes" : sp.get("tab") === "plantillas" ? "plantillas" : "asuntos");
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState<any>(null);  // {asunto_id?} abre el modal
  const cargar = useCallback(() => api.get("/connect/resumen").then(setR).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const [filtro, setFiltro] = useState("todos");
  const lista = (r?.asuntos || []).filter((a: any) => filtro === "todos" ? true : filtro === "sin" ? !a.seguimiento_id
    : filtro === "atrasados" ? a.seguimiento_id && (a.dias_sin_actualizar ?? 0) >= 15 && a.estado === "activo" : a.seguimiento_id);
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Tu cliente informado. Tu tiempo, de vuelta.</p>
          <h1 className="text-3xl font-extrabold text-marino">Nomira Connect</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Su cliente ve en qué etapa va su asunto desde el celular y le escribe por aquí, sin llamadas ni mensajes sueltos.</p></div>
        <div className="flex items-center gap-2"><BotonAyuda modulo="connect" />
          <button className="btn-turquesa" onClick={() => setNuevo({})}>+ Nuevo seguimiento</button></div>
      </div>
      <Aviso>{error}</Aviso>
      {r && <div className="mb-5 grid gap-3 sm:grid-cols-4">
        {[["Con seguimiento", r.cifras.con_seguimiento, "con"], ["Publicados al cliente", r.cifras.publicados, "con"],
          ["Sin actualizar 15+ días", r.cifras.sin_actualizar_15, "atrasados"], ["Mensajes nuevos", r.mensajes_nuevos, "mensajes"]].map(([t, n, f]) => (
          <button key={t as string} onClick={() => f === "mensajes" ? setTab("mensajes") : (setTab("asuntos"), setFiltro(f as string))}
            className={`tarjeta p-4 text-left transition hover:-translate-y-0.5 ${f === "mensajes" && Number(n) > 0 ? "ring-2 ring-amber-300" : ""}`}>
            <span className="block text-2xl font-extrabold text-marino">{n as number}</span><span className="text-xs text-slate-500">{t}</span></button>))}
      </div>}
      <div className="mb-4 flex rounded-xl bg-crema p-1 text-sm">
        {([["asuntos", "Asuntos"], ["mensajes", `Mensajes${r?.mensajes_nuevos ? ` (${r.mensajes_nuevos})` : ""}`], ["plantillas", "Plantillas de etapas"]] as const).map(([v, t]) =>
          <button key={v} onClick={() => setTab(v)} className={`flex-1 rounded-lg px-3 py-2 font-semibold sm:flex-none ${tab === v ? "bg-white text-marino shadow-sm" : "text-slate-500"}`}>{t}</button>)}
      </div>

      {tab === "asuntos" && r && <>
        <div className="mb-3 flex flex-wrap gap-2 text-xs">{[["todos", "Todos"], ["con", "Con seguimiento"], ["sin", "Sin seguimiento"], ["atrasados", "Sin actualizar 15+ días"]].map(([v, t]) =>
          <button key={v} onClick={() => setFiltro(v)} className={`rounded-full border px-3 py-1 font-semibold ${filtro === v ? "border-marino bg-marino text-white" : "border-crema-300 bg-white text-slate-600"}`}>{t}</button>)}</div>
        {!r.asuntos.length ? (
          <div className="tarjeta p-10 text-center"><p className="text-lg font-bold text-marino">Empiece con su primer seguimiento</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">Elija una plantilla (laboral, pensiones, amparo, familiar…), ajuste las etapas y publíquelo para que su cliente lo vea en su celular.</p>
            <button className="btn-turquesa mt-4" onClick={() => setNuevo({})}>+ Nuevo seguimiento</button></div>
        ) : (
          <div className="tarjeta divide-y divide-crema-300 overflow-hidden">
            {lista.map((a: any) => {
              const est = a.etapa_estado ? ESTADO_ETAPA[a.etapa_estado] : null;
              return (
                <div key={a.asunto_id} className="flex flex-wrap items-center gap-3 p-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-bold text-marino">{a.asunto}{a.numero && <span className="ml-2 text-xs font-normal text-slate-500">{a.numero}</span>}</p>
                    <p className="text-xs text-slate-500">{a.cliente || <span className="text-amber-700">Sin cliente vinculado</span>} · {a.materia}{a.responsable && ` · ${a.responsable}`}</p>
                  </div>
                  {a.seguimiento_id ? <>
                    {est && <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${est.chip}`}>{a.etapa}</span>}
                    {a.estado !== "activo" && <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{a.estado === "cerrado" ? "Concluido" : "Suspendido"}</span>}
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${a.visible ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{a.visible ? "Publicado" : "Borrador"}</span>
                    {(a.dias_sin_actualizar ?? 0) >= 15 && a.estado === "activo" && <span className="text-xs font-semibold text-amber-700" title="Días desde la última actualización visible para el cliente">{a.dias_sin_actualizar} días sin actualizar</span>}
                    <Link href={`/connect/${a.seguimiento_id}`} className="btn-sec text-sm">Abrir</Link>
                  </> : <button className="btn-sec text-sm" onClick={() => setNuevo({ asunto_id: a.asunto_id, titulo: a.asunto })}>Crear seguimiento</button>}
                </div>);
            })}
            {!lista.length && <p className="p-6 text-center text-sm text-slate-500">Nada con este filtro.</p>}
          </div>)}
      </>}
      {tab === "mensajes" && <Mensajes inicial={sp.get("cliente")} onCambio={cargar} />}
      {tab === "plantillas" && <Plantillas />}
      {nuevo && r && <NuevoSeguimiento datos={nuevo} materias={r.materias} onCerrar={() => setNuevo(null)} onListo={(id) => router.push(`/connect/${id}`)} />}
    </Shell>
  );
}

function NuevoSeguimiento({ datos, materias, onCerrar, onListo }: { datos: any; materias: Record<string, string>; onCerrar: () => void; onListo: (id: number) => void }) {
  const [p, setP] = useState<any>(null);
  const [clientes, setClientes] = useState<any[]>([]);
  const [f, setF] = useState({ titulo: "", numero: "", cliente_id: "", materia: "laboral", plantilla: "base:laboral" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => {
    api.get("/connect/plantillas").then(setP).catch((e) => setError(e.message));
    if (!datos.asunto_id) api.get("/clientes").then((x) => setClientes(x.clientes || [])).catch(() => {});
  }, [datos.asunto_id]);
  const elegida = p && (f.plantilla.startsWith("base:") ? p.base.find((b: any) => "base:" + b.clave === f.plantilla) : p.propias.find((x: any) => "p:" + x.id === f.plantilla));
  const crear = async () => {
    setEnviando(true); setError("");
    try {
      const cuerpo: any = f.plantilla.startsWith("base:") ? { base: f.plantilla.slice(5) } : { plantilla_id: Number(f.plantilla.slice(2)) };
      if (datos.asunto_id) cuerpo.asunto_id = datos.asunto_id;
      else Object.assign(cuerpo, { titulo: f.titulo, numero: f.numero || null, cliente_id: f.cliente_id ? Number(f.cliente_id) : null, materia: f.materia });
      const r = await api.post("/connect/seguimientos", cuerpo);
      onListo(r.id);
    } catch (e: any) { setError(e.message); setEnviando(false); }
  };
  return (
    <Modal titulo={datos.asunto_id ? `Seguimiento de «${datos.titulo}»` : "Nuevo seguimiento"} onCerrar={onCerrar} ancho="max-w-2xl">
      <Aviso>{error}</Aviso>
      {!datos.asunto_id && <div className="grid gap-3 sm:grid-cols-2">
        <label className="sm:col-span-2"><span className="etiqueta">Nombre del asunto</span><input className="campo" value={f.titulo} onChange={(e) => setF({ ...f, titulo: e.target.value })} placeholder="Ej. Pensión ISSEMYM de María López" /></label>
        <label><span className="etiqueta">Número de expediente (opcional)</span><input className="campo" value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value })} /></label>
        <label><span className="etiqueta">Materia</span><select className="campo" value={f.materia} onChange={(e) => setF({ ...f, materia: e.target.value })}>{Object.entries(materias).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="sm:col-span-2"><span className="etiqueta">Cliente (de su directorio)</span>
          <select className="campo" value={f.cliente_id} onChange={(e) => setF({ ...f, cliente_id: e.target.value })}>
            <option value="">— Elegir después —</option>{clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select>
          <span className="mt-1 block text-xs text-slate-500">Para que el cliente lo vea en su portal, el asunto debe estar vinculado a él. ¿No está? <Link href="/clientes" className="font-semibold text-turquesa-700 underline">Dé de alta al cliente</Link>.</span></label>
      </div>}
      <label className="mt-3 block"><span className="etiqueta">Plantilla de etapas</span>
        <select className="campo" value={f.plantilla} onChange={(e) => setF({ ...f, plantilla: e.target.value })}>
          {p?.propias.length > 0 && <optgroup label="De su despacho">{p.propias.map((x: any) => <option key={x.id} value={"p:" + x.id}>{x.nombre}</option>)}</optgroup>}
          <optgroup label="Plantillas de Nomira">{p?.base.map((b: any) => <option key={b.clave} value={"base:" + b.clave}>{b.nombre}</option>)}</optgroup>
        </select></label>
      {elegida && <div className="mt-3 rounded-xl bg-crema/70 p-3"><p className="mb-2 text-xs font-semibold text-slate-500">Etapas ({elegida.etapas.length}) — podrá cambiarlas solo para este asunto:</p>
        <ol className="flex flex-wrap gap-1.5">{elegida.etapas.map((e: any, i: number) => <li key={i} className="rounded-full bg-white px-2.5 py-1 text-xs text-marino">{i + 1}. {e.nombre}{e.opcional && <span className="text-slate-400"> (si aplica)</span>}</li>)}</ol></div>}
      <p className="mt-3 text-xs text-slate-500">El seguimiento se crea como <b>borrador</b>: el cliente no lo ve hasta que usted lo publique.</p>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
        <button className="btn-turquesa" disabled={enviando || (!datos.asunto_id && !f.titulo.trim())} onClick={crear}>{enviando ? "Creando…" : "Crear seguimiento"}</button></div>
    </Modal>
  );
}

function Mensajes({ inicial, onCambio }: { inicial: string | null; onCambio: () => void }) {
  const [b, setB] = useState<any>(null);
  const [sel, setSel] = useState<number | null>(inicial ? Number(inicial) : null);
  const [hilo, setHilo] = useState<any>(null);
  const [texto, setTexto] = useState("");
  const [error, setError] = useState("");
  const fin = useRef<HTMLDivElement>(null);
  const cargar = useCallback(() => api.get("/connect/mensajes").then(setB).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const abrir = useCallback((cid: number) => api.get(`/connect/mensajes/${cid}`).then((h) => { setHilo(h); cargar(); onCambio(); }).catch((e) => setError(e.message)), [cargar, onCambio]);
  useEffect(() => { if (sel) abrir(sel); }, [sel, abrir]);
  useEffect(() => { fin.current?.scrollIntoView({ block: "end" }); }, [hilo]);
  const enviar = async () => {
    if (!texto.trim() || !sel) return;
    try { await api.post(`/connect/mensajes/${sel}`, { texto }); setTexto(""); abrir(sel); } catch (e: any) { setError(e.message); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="tarjeta max-h-[70vh] divide-y divide-crema-300 overflow-y-auto">
        {b && !b.hilos.length && <p className="p-6 text-sm text-slate-500">Aún no hay mensajes. Cuando un cliente le escriba desde su portal, aparecerá aquí y le avisaremos por correo.</p>}
        {b?.hilos.map((h: any) => (
          <button key={h.cliente_id} onClick={() => setSel(h.cliente_id)} className={`block w-full p-3 text-left transition hover:bg-crema/60 ${sel === h.cliente_id ? "bg-crema" : ""}`}>
            <div className="flex items-center justify-between gap-2"><span className="truncate font-bold text-marino">{h.cliente}</span>
              {h.nuevos > 0 && <span className="rounded-full bg-amber-400 px-2 text-xs font-bold text-marino-900">{h.nuevos}</span>}</div>
            {h.motivo && <span className="text-[11px] font-semibold text-amber-700">{h.motivo}</span>}
            <p className="truncate text-xs text-slate-500">{h.autor === "despacho" ? "Usted: " : ""}{h.ultimo}</p>
            <p className="text-[11px] text-slate-400">{fechaHora(h.fecha)}</p></button>))}
      </div>
      <div className="tarjeta flex min-h-[50vh] flex-col">
        <Aviso>{error}</Aviso>
        {!hilo ? <p className="m-auto p-8 text-sm text-slate-500">Elija una conversación.</p> : <>
          <div className="flex items-center justify-between border-b border-crema-300 p-4"><p className="font-bold text-marino">{hilo.cliente.nombre}</p>
            {hilo.mensajes.some((x: any) => x.autor === "cliente" && x.estado === "nuevo") &&
              <button className="btn-sec text-xs" onClick={() => api.post(`/connect/mensajes/${sel}/atendido`, {}).then(() => abrir(sel!))}>Marcar como atendido</button>}</div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4" style={{ maxHeight: "55vh" }}>
            {hilo.mensajes.map((x: any) => (
              <div key={x.id} className={`flex ${x.autor === "despacho" ? "justify-end" : ""}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${x.autor === "despacho" ? "bg-marino text-white" : "bg-crema text-marino"}`}>
                  {x.motivo && x.autor === "cliente" && <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-amber-700">{x.motivo}{x.asunto && ` · ${x.asunto}`}</p>}
                  <p className="whitespace-pre-wrap">{x.texto}</p>
                  <p className={`mt-1 text-[10px] ${x.autor === "despacho" ? "text-white/60" : "text-slate-400"}`}>{x.por ? `${x.por} · ` : ""}{fechaHora(x.fecha)}{x.autor === "despacho" && (x.leido ? " · Leído" : "")}</p>
                </div></div>))}
            <div ref={fin} />
          </div>
          <div className="flex gap-2 border-t border-crema-300 p-3">
            <textarea className="campo min-h-[44px] flex-1" rows={2} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Escriba su respuesta. Su cliente la verá en su portal." />
            <button className="btn-turquesa self-end" disabled={!texto.trim()} onClick={enviar}>Enviar</button></div>
          <p className="px-3 pb-3 text-[11px] text-slate-500">El cliente ve la respuesta al entrar a su portal. (Los avisos automáticos por WhatsApp llegan en la siguiente fase.)</p>
        </>}
      </div>
    </div>
  );
}

function Plantillas() {
  const [p, setP] = useState<any>(null);
  const [editar, setEditar] = useState<any>(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.get("/connect/plantillas").then(setP).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  return (
    <div>
      <Aviso>{error}</Aviso>
      <div className="mb-3 flex items-center justify-between"><p className="text-sm text-slate-500">Las plantillas son una guía: cada asunto puede tener sus propias etapas sin cambiar la plantilla.</p>
        <button className="btn-sec text-sm" onClick={() => setEditar({ nombre: "", especialidad: "laboral", etapas: [{ nombre: "" }] })}>+ Plantilla en blanco</button></div>
      {p?.propias.length > 0 && <><h2 className="mb-2 mt-4 text-sm font-bold uppercase tracking-wider text-slate-500">De su despacho</h2>
        <div className="grid gap-3 md:grid-cols-2">{p.propias.map((x: any) => (
          <div key={x.id} className="tarjeta p-4"><div className="flex items-start justify-between gap-2"><p className="font-bold text-marino">{x.nombre}</p>
            <div className="flex gap-1"><button className="btn-sec text-xs" onClick={() => setEditar(x)}>Editar</button>
              <button className="btn-sec text-xs" onClick={() => api.borrar(`/connect/plantillas/${x.id}`).then(cargar)}>Borrar</button></div></div>
            <p className="mt-1 text-xs text-slate-500">{x.etapas.map((e: any) => e.nombre).join(" → ")}</p></div>))}</div></>}
      <h2 className="mb-2 mt-5 text-sm font-bold uppercase tracking-wider text-slate-500">Plantillas de Nomira</h2>
      <div className="grid gap-3 md:grid-cols-2">{p?.base.map((b: any) => (
        <div key={b.clave} className="tarjeta p-4"><div className="flex items-start justify-between gap-2">
          <div><p className="font-bold text-marino">{b.nombre}</p>{b.nota && <p className="text-[11px] text-slate-500">{b.nota}</p>}</div>
          <button className="btn-sec shrink-0 text-xs" onClick={() => setEditar({ nombre: `${b.nombre} (mi despacho)`, especialidad: b.clave, etapas: b.etapas })}>Duplicar y editar</button></div>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">{b.etapas.map((e: any) => e.nombre).join(" → ")}</p></div>))}</div>
      {editar && <EditorPlantilla p={editar} onCerrar={() => setEditar(null)} onListo={() => { setEditar(null); cargar(); }} />}
    </div>
  );
}

function EditorPlantilla({ p, onCerrar, onListo }: { p: any; onCerrar: () => void; onListo: () => void }) {
  const [nombre, setNombre] = useState(p.nombre);
  const [etapas, setEtapas] = useState<any[]>(p.etapas.map((e: any) => ({ ...e })));
  const [error, setError] = useState("");
  const guardar = async () => {
    try {
      const cuerpo = { nombre, especialidad: p.especialidad, etapas };
      if (p.id) await api.put(`/connect/plantillas/${p.id}`, cuerpo); else await api.post("/connect/plantillas", cuerpo);
      onListo();
    } catch (e: any) { setError(e.message); }
  };
  return (
    <Modal titulo={p.id ? "Editar plantilla" : "Nueva plantilla"} onCerrar={onCerrar} ancho="max-w-2xl">
      <Aviso>{error}</Aviso>
      <label className="mb-3 block"><span className="etiqueta">Nombre</span><input className="campo" value={nombre} onChange={(e) => setNombre(e.target.value)} /></label>
      <EditorEtapas etapas={etapas} setEtapas={setEtapas} />
      <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
        <button className="btn-turquesa" disabled={!nombre.trim()} onClick={guardar}>Guardar plantilla</button></div>
    </Modal>
  );
}

export default function Pagina() { return <Suspense><Connect /></Suspense>; }
