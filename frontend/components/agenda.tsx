"use client";
import Link from "next/link";
import BotonAyuda from "@/components/BotonAyuda";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { type ClienteBreve, SelectorCliente } from "@/components/clientes";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha } from "@/lib/api";

/** Marco de Nomira Agenda Jurídica: submenú del módulo y aviso permanente sobre el cálculo asistido. */
export function AgendaShell({ children }: { children: React.ReactNode }) {
  const ruta = usePathname();
  const enlaces: [string, string, boolean][] = [
    ["/agenda", "Hoy", ruta === "/agenda"], ["/agenda/calendario", "Calendario", ruta.startsWith("/agenda/calendario")],
    ["/agenda/asuntos", "Asuntos", ruta.startsWith("/agenda/asuntos")], ["/agenda/pendientes", "Todos los pendientes", ruta.startsWith("/agenda/pendientes")],
    ["/agenda/estrados", "Estrados", ruta.startsWith("/agenda/estrados")],
    ["/agenda/calendarios", "Días hábiles", ruta.startsWith("/agenda/calendarios")], ["/agenda/configuracion", "Avisos y ajustes", ruta.startsWith("/agenda/configuracion")],
  ];
  return (
    <Shell>
      <div className="mb-1 flex items-center justify-between gap-2"><p className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">Nomira Agenda Jurídica</p><BotonAyuda modulo="agenda" /></div>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-crema-300" aria-label="Nomira Agenda">
        {enlaces.map(([href, t, activo]) => (
          <Link key={href} href={href} aria-current={activo ? "page" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${activo ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>{t}</Link>))}
      </nav>
      {children}
      <p className="mt-10 text-center text-xs text-slate-400">Nomira ayuda a calcular y recordar. Los plazos calculados son un apoyo: el abogado los valida conforme a la ley aplicable y al calendario oficial del tribunal.</p>
    </Shell>
  );
}

let cache: any = null;
const subs = new Set<(c: any) => void>();
export function useCatalogosAgenda(): any {
  const [c, setC] = useState<any>(cache);
  useEffect(() => { subs.add(setC); if (!cache) recargarCatalogosAgenda(); return () => { subs.delete(setC); }; }, []);
  return c;
}
export function recargarCatalogosAgenda() {
  return api.get("/agenda/catalogos").then((x) => { cache = x; subs.forEach((f) => f(x)); return x; }).catch(() => null);
}

export const SITUACION: Record<string, [string, string]> = {
  vencido: ["Vencido", "bg-red-100 text-red-800"], hoy: ["Hoy", "bg-amber-100 text-amber-900"], proximo: ["Próximo", "bg-turquesa-50 text-turquesa-700"],
  futuro: ["Programado", "bg-slate-100 text-slate-700"], cumplido: ["Cumplido", "bg-emerald-100 text-emerald-800"], cancelado: ["Cancelado", "bg-slate-200 text-slate-600"],
};
const PRIORIDAD: Record<string, string> = { alta: "bg-orange-100 text-orange-800", critica: "bg-red-600 text-white" };
const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];

export function diaLargo(iso: string) {
  const [a, m, d] = iso.split("-").map(Number);
  const f = new Date(a, m - 1, d);
  return `${DIAS[f.getDay()]} ${fecha(iso)}`;
}

export function Etq({ clase, children }: { clase: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${clase}`}>{children}</span>;
}

export function faltanTexto(e: any) {
  if (e.estado !== "pendiente") return SITUACION[e.estado][0];
  if (e.faltan < 0) return `Venció hace ${-e.faltan} día(s)`;
  if (e.faltan === 0) return "Hoy";
  if (e.faltan === 1) return "Mañana";
  return `En ${e.faltan} días`;
}

/** Renglón de un plazo, audiencia o actividad con acciones rápidas. */
export function FilaEvento({ e, onCambio, mostrarAsunto = true }: { e: any; onCambio?: () => void; mostrarAsunto?: boolean }) {
  const cat = useCatalogosAgenda();
  const [err, setErr] = useState("");
  const accion = (ruta: string, cuerpo: any = {}) => api.post(`/agenda/eventos/${e.id}/${ruta}`, cuerpo).then(() => onCambio?.()).catch((x) => setErr(x.message));
  const [s, c] = SITUACION[e.situacion];
  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Etq clase={c}>{e.situacion === "vencido" || e.situacion === "hoy" ? faltanTexto(e) : s}</Etq>
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{e.tipo_texto}</span>
          {PRIORIDAD[e.prioridad] && <Etq clase={PRIORIDAD[e.prioridad]}>{e.prioridad === "critica" ? "Crítica" : "Alta"}</Etq>}
          {e.por_validar && e.calculo && <Etq clase="bg-violet-100 text-violet-800">Cálculo sin validar</Etq>}
          {e.por_validar && !e.calculo && <Etq clase="bg-slate-100 text-slate-600">Fecha sin validar</Etq>}
        </div>
        <Link href={`/agenda/eventos/${e.id}`} className="mt-1 block font-semibold text-marino hover:underline">{e.titulo}</Link>
        <p className="text-sm text-slate-600">{diaLargo(e.fecha)}{e.hora ? ` · ${e.hora} h` : ""}{e.situacion !== "vencido" && e.situacion !== "hoy" && e.estado === "pendiente" ? ` · ${faltanTexto(e)}` : ""}
          {mostrarAsunto && e.asunto && <> · <Link className="hover:underline" href={`/agenda/asuntos/${e.asunto.id}`}>{e.asunto.titulo}{e.asunto.numero ? ` (${e.asunto.numero})` : ""}</Link></>}</p>
        <p className="text-xs text-slate-500">{e.responsable ? `Responsable: ${e.responsable}` : <span className="font-semibold text-red-700">Sin responsable</span>}{e.apoyo.length ? ` · Apoyo: ${e.apoyo.join(", ")}` : ""}</p>
        {err && <p className="mt-1 text-xs text-red-700">{err}</p>}
      </div>
      {e.estado === "pendiente" && <div className="flex flex-wrap gap-2 sm:justify-end">
        {e.enlace && <a className="btn-sec py-1 text-xs" href={e.enlace} target="_blank" rel="noopener noreferrer">Unirse{e.plataforma ? ` (${e.plataforma.nombre})` : ""}</a>}
        {e.por_validar && cat?.puede_editar && <button className="btn-sec py-1 text-xs" onClick={() => accion("validar")}>Validar</button>}
        {(cat?.puede_editar || e.responsable_id === cat?.yo) && <button className="btn-turquesa py-1 text-xs" onClick={() => accion("cumplir")}>Cumplido</button>}
      </div>}
    </li>
  );
}

export function ListaEventos({ titulo, eventos, vacio, onCambio, tono = "" }: { titulo: string; eventos: any[]; vacio: string; onCambio: () => void; tono?: string }) {
  return (
    <section className={`tarjeta overflow-hidden ${tono}`}>
      <h2 className="border-b border-crema-300 px-4 py-3 font-semibold text-marino">{titulo} <span className="text-slate-400">({eventos.length})</span></h2>
      {eventos.length ? <ul className="divide-y divide-crema-200">{eventos.map((e) => <FilaEvento key={e.id} e={e} onCambio={onCambio} />)}</ul>
        : <p className="px-4 py-4 text-sm text-slate-500">{vacio}</p>}
    </section>
  );
}

/** Desglose del cálculo asistido: qué días se contaron y cuáles se saltaron. */
export function Desglose({ r }: { r: any }) {
  const [ver, setVer] = useState(false);
  return (
    <div className="rounded-xl border border-violet-200 bg-violet-50/60 p-4 text-sm">
      <p className="text-base">Vence el <b className="text-marino">{diaLargo(r.vence)}</b></p>
      {r.ajuste_manual && <p className="mt-1 font-semibold text-amber-800">El abogado fijó otra fecha: {diaLargo(r.ajuste_manual)}.</p>}
      <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-slate-700">{r.pasos.map((p: string, i: number) => <li key={i}>{p}</li>)}</ol>
      <p className="mt-2 text-xs text-slate-600">Calendario: {r.calendario}</p>
      {r.advertencia && <p className="mt-1 text-xs font-semibold text-amber-800">{r.advertencia}</p>}
      <button type="button" className="mt-2 text-xs font-semibold text-turquesa-700 underline" onClick={() => setVer(!ver)}>{ver ? "Ocultar" : "Ver"} días contados y saltados</button>
      {ver && <div className="mt-2 grid gap-3 sm:grid-cols-2">
        <div><p className="text-xs font-semibold text-slate-600">Contados ({r.contados.length})</p>
          <ol className="mt-1 max-h-48 list-decimal overflow-auto pl-6 text-xs">{r.contados.map((d: string) => <li key={d}>{diaLargo(d)}</li>)}</ol></div>
        <div><p className="text-xs font-semibold text-slate-600">Inhábiles saltados ({r.saltados.length})</p>
          <ul className="mt-1 max-h-48 overflow-auto text-xs">{r.saltados.map((s: any) => <li key={s.fecha}>{diaLargo(s.fecha)} — {s.motivo}</li>)}</ul></div>
      </div>}
      <p className="mt-3 text-xs text-violet-900">{r.aviso}</p>
    </div>
  );
}

const vacioEvento = (tipo = "plazo", extra: any = {}) => ({
  tipo, titulo: "", descripcion: "", asunto_id: "", actuacion_id: null, fecha: "", hora: "", duracion_min: "", lugar: "", enlace: "",
  prioridad: "normal", responsable_id: "", apoyo_ids: [] as number[], alertas: null as number[] | null, usarCalculo: tipo === "plazo",
  calculo: { notificacion: "", dias: "", tipo_dias: "habiles", surte_efectos: "", recorrer_inhabil: true }, plantilla: "", ...extra,
});

/** Alta o edición de plazo, audiencia o actividad, con cálculo asistido de días. */
export function FormEvento({ inicial, asuntoFijo, onCerrar, onGuardado }: { inicial?: any; asuntoFijo?: any; onCerrar: () => void; onGuardado: (e: any) => void }) {
  const cat = useCatalogosAgenda();
  const [asuntos, setAsuntos] = useState<any[]>(asuntoFijo ? [asuntoFijo] : []);
  const [f, setF] = useState<any>(() => {
    if (!inicial?.id) return vacioEvento(inicial?.tipo, { asunto_id: asuntoFijo?.id ?? "", ...(inicial || {}),
      calculo: { ...vacioEvento().calculo, ...(inicial?.calculo || {}) } });
    const c = inicial.calculo;
    return { ...vacioEvento(inicial.tipo), ...inicial, asunto_id: inicial.asunto?.id ?? "", responsable_id: inicial.responsable_id ?? "",
      hora: inicial.hora || "", duracion_min: inicial.duracion_min ?? "", lugar: inicial.lugar || "", enlace: inicial.enlace || "", descripcion: inicial.descripcion || "",
      alertas: inicial.alertas_propias ? inicial.alertas : null, usarCalculo: !!c, fecha: c ? (c.ajuste_manual || "") : inicial.fecha,
      calculo: c ? { notificacion: c.notificacion, dias: c.dias, tipo_dias: c.tipo_dias, surte_efectos: c.surte_efectos, recorrer_inhabil: c.recorrer_inhabil } : vacioEvento().calculo };
  });
  const [prev, setPrev] = useState<any>(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => { if (!asuntoFijo) api.get("/agenda/asuntos").then(setAsuntos).catch(() => {}); }, [asuntoFijo]);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const setC = (k: string, v: any) => setF({ ...f, calculo: { ...f.calculo, [k]: v } });
  const calcListo = f.calculo.notificacion && Number(f.calculo.dias) > 0 && f.calculo.surte_efectos;
  const calculoBody = () => ({ ...f.calculo, dias: Number(f.calculo.dias), asunto_id: f.asunto_id ? Number(f.asunto_id) : null });
  useEffect(() => {
    if (f.tipo !== "plazo" || !f.usarCalculo || !calcListo) { setPrev(null); return; }
    const t = setTimeout(() => api.post("/agenda/calcular", calculoBody()).then(setPrev).catch((e) => { setPrev(null); setError(e.message); }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.calculo, f.asunto_id, f.tipo, f.usarCalculo]);
  function plantilla(id: string) {
    const p = cat?.plantillas.find((x: any) => String(x.id) === id);
    if (!p) return setF({ ...f, plantilla: "" });
    setF({ ...f, plantilla: id, titulo: f.titulo || p.nombre, usarCalculo: true, alertas: p.alertas ?? f.alertas,
      descripcion: f.descripcion || (p.fundamento ? `Fundamento: ${p.fundamento}` : ""),
      calculo: { ...f.calculo, dias: p.dias, tipo_dias: p.tipo_dias, surte_efectos: p.surte_efectos } });
  }
  async function guardar(ev: React.FormEvent) {
    ev.preventDefault(); setError(""); setGuardando(true);
    const usar = f.tipo === "plazo" && f.usarCalculo;
    const cuerpo: any = { tipo: f.tipo, titulo: f.titulo, descripcion: f.descripcion || null, asunto_id: f.asunto_id ? Number(f.asunto_id) : null,
      actuacion_id: f.actuacion_id || null, fecha: f.fecha || null, hora: f.hora || null, duracion_min: f.duracion_min ? Number(f.duracion_min) : null,
      lugar: f.lugar || null, enlace: f.enlace || null, prioridad: f.prioridad, responsable_id: f.responsable_id ? Number(f.responsable_id) : null,
      apoyo_ids: f.apoyo_ids, alertas: f.alertas, calculo: usar ? calculoBody() : null };
    try {
      const r = inicial?.id ? await api.patch(`/agenda/eventos/${inicial.id}`, cuerpo) : await api.post("/agenda/eventos", cuerpo);
      onGuardado(r);
    } catch (e: any) { setError(e.message); } finally { setGuardando(false); }
  }
  if (!cat) return null;
  const defecto = f.tipo === "audiencia" ? cat.alertas_audiencia : cat.alertas_plazo;
  const alertas = f.alertas ?? defecto;
  return (
    <Modal titulo={inicial?.id ? "Editar" : "Nuevo pendiente en la agenda"} onCerrar={onCerrar} ancho="max-w-3xl">
      <form onSubmit={guardar} className="space-y-4">
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Tipo">
          {Object.entries(cat.tipos_evento).map(([k, t]: any) => <button type="button" key={k} role="radio" aria-checked={f.tipo === k}
            className={`rounded-full border px-4 py-1.5 text-sm font-semibold ${f.tipo === k ? "border-turquesa bg-turquesa-50 text-marino" : "border-crema-300 text-slate-600"}`}
            onClick={() => setF({ ...f, tipo: k, usarCalculo: k === "plazo" && f.usarCalculo })}>{t}</button>)}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="sm:col-span-2"><span className="etiqueta">Qué hay que hacer</span><input className="campo" required minLength={3} maxLength={200} value={f.titulo} onChange={set("titulo")}
            placeholder={f.tipo === "audiencia" ? "Ej. Audiencia preliminar" : f.tipo === "plazo" ? "Ej. Contestar requerimiento" : "Ej. Revisar lista de acuerdos"} /></label>
          {!asuntoFijo && <label><span className="etiqueta">Asunto (opcional)</span><select className="campo" value={f.asunto_id} onChange={set("asunto_id")}>
            <option value="">Sin asunto</option>{asuntos.map((a) => <option key={a.id} value={a.id}>{a.titulo}{a.numero ? ` · ${a.numero}` : ""}</option>)}</select></label>}
          <label><span className="etiqueta">Responsable</span><select className="campo" value={f.responsable_id} onChange={set("responsable_id")}>
            <option value="">Sin asignar</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Prioridad</span><select className="campo" value={f.prioridad} onChange={set("prioridad")}>
            {Object.entries(cat.prioridades).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        </div>

        {f.tipo === "plazo" && <fieldset className="rounded-xl border border-crema-300 p-4">
          <legend className="px-1 text-sm font-semibold text-marino">Fecha de vencimiento</legend>
          <div className="mb-3 flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="radio" className="accent-turquesa" checked={f.usarCalculo} onChange={() => setF({ ...f, usarCalculo: true })} />Calcular a partir de la notificación</label>
            <label className="flex items-center gap-2"><input type="radio" className="accent-turquesa" checked={!f.usarCalculo} onChange={() => setF({ ...f, usarCalculo: false })} />Capturar la fecha directamente</label>
          </div>
          {f.usarCalculo ? <>
            {cat.plantillas.length > 0 && <label className="mb-3 block"><span className="etiqueta">Plazo frecuente del despacho (opcional)</span>
              <select className="campo" value={f.plantilla} onChange={(e) => plantilla(e.target.value)}><option value="">Elegir…</option>
                {cat.plantillas.map((p: any) => <option key={p.id} value={p.id}>{p.nombre} · {p.dias} {p.tipo_dias === "habiles" ? "días hábiles" : "días naturales"}</option>)}</select></label>}
            <div className="grid gap-3 sm:grid-cols-4">
              <label><span className="etiqueta">Fecha de notificación</span><input className="campo" type="date" value={f.calculo.notificacion} onChange={(e) => setC("notificacion", e.target.value)} /></label>
              <label><span className="etiqueta">Días de plazo</span><input className="campo" type="number" min={1} max={400} value={f.calculo.dias} onChange={(e) => setC("dias", e.target.value)} /></label>
              <label><span className="etiqueta">Tipo de días</span><select className="campo" value={f.calculo.tipo_dias} onChange={(e) => setC("tipo_dias", e.target.value)}>
                {Object.entries(cat.tipos_dias).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
              <label><span className="etiqueta">La notificación surte efectos</span><select className="campo" value={f.calculo.surte_efectos} onChange={(e) => setC("surte_efectos", e.target.value)}>
                <option value="">Elija…</option>{Object.entries(cat.surte_efectos).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
            </div>
            {f.calculo.tipo_dias === "naturales" && <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={f.calculo.recorrer_inhabil}
              onChange={(e) => setC("recorrer_inhabil", e.target.checked)} />Si el último día es inhábil, recorrer al siguiente día hábil</label>}
            {prev && <div className="mt-3"><Desglose r={prev} /></div>}
            {prev && <label className="mt-3 block max-w-xs"><span className="etiqueta">¿Otra fecha? (opcional, queda anotado)</span><input className="campo" type="date" value={f.fecha} onChange={set("fecha")} /></label>}
          </> : <label className="block max-w-xs"><span className="etiqueta">Vence el</span><input className="campo" type="date" required value={f.fecha} onChange={set("fecha")} /></label>}
        </fieldset>}

        {f.tipo !== "plazo" && <div className="grid gap-3 sm:grid-cols-3">
          <label><span className="etiqueta">Fecha</span><input className="campo" type="date" required value={f.fecha} onChange={set("fecha")} /></label>
          <label><span className="etiqueta">Hora</span><input className="campo" type="time" value={f.hora} onChange={set("hora")} /></label>
          <label><span className="etiqueta">Duración (min)</span><input className="campo" type="number" min={5} value={f.duracion_min} onChange={set("duracion_min")} /></label>
          {f.tipo === "audiencia" && <>
            <label className="sm:col-span-2"><span className="etiqueta">Lugar o sala</span><input className="campo" value={f.lugar} onChange={set("lugar")} /></label>
            <label><span className="etiqueta">Enlace (Zoom, Meet, Teams)</span><input className="campo" type="url" placeholder="https://" value={f.enlace} onChange={set("enlace")} /></label>
          </>}
        </div>}

        <details className="rounded-xl border border-crema-300 p-3 text-sm">
          <summary className="cursor-pointer font-semibold text-marino">Apoyo, avisos y notas</summary>
          <div className="mt-3 space-y-3">
            <div><span className="etiqueta">Personas de apoyo (también reciben avisos)</span>
              <div className="flex flex-wrap gap-3">{cat.usuarios.filter((u: any) => String(u.id) !== String(f.responsable_id)).map((u: any) => <label key={u.id} className="flex items-center gap-1.5">
                <input type="checkbox" className="accent-turquesa" checked={f.apoyo_ids.includes(u.id)}
                  onChange={() => setF({ ...f, apoyo_ids: f.apoyo_ids.includes(u.id) ? f.apoyo_ids.filter((x: number) => x !== u.id) : [...f.apoyo_ids, u.id] })} />{u.nombre}</label>)}</div></div>
            <label className="block"><span className="etiqueta">Avisar estos días antes (separados por coma; 0 = el mismo día)</span>
              <input className="campo max-w-xs" value={alertas.join(", ")} onChange={(e) => setF({ ...f, alertas: e.target.value.split(",").map((x) => parseInt(x.trim())).filter((x) => !isNaN(x)) })} />
              <span className="mt-1 block text-xs text-slate-500">Si el día del vencimiento sigue pendiente a mediodía, se avisa también a quien supervisa; si vence sin cumplirse, a ambos.</span></label>
            <label className="block"><span className="etiqueta">Notas</span><textarea className="campo" rows={3} value={f.descripcion} onChange={set("descripcion")} /></label>
          </div>
        </details>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={guardando || (f.tipo === "plazo" && f.usarCalculo && !prev)}>{guardando ? "Guardando…" : "Guardar"}</button></div>
      </form>
    </Modal>
  );
}

/** Alta o edición de un asunto (juicio o procedimiento). */
export function FormAsunto({ inicial, onCerrar, onGuardado }: { inicial?: any; onCerrar: () => void; onGuardado: (a: any) => void }) {
  const cat = useCatalogosAgenda();
  const [f, setF] = useState<any>({ titulo: "", numero: "", jurisdiccion: "federal", entidad: "", tribunal: "", materia: "", calendario_id: cat?.calendario_defecto ?? "",
    responsable_id: "", expediente_id: "", ev_asunto_id: "", notas: "", ...(inicial || {}) });
  const [error, setError] = useState("");
  const [cliente, setCliente] = useState<ClienteBreve | null>(inicial?.cr_cliente_id ? { id: inicial.cr_cliente_id, nombre: inicial.cliente || "Cliente" } : null);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  if (!cat) return null;
  async function guardar(ev: React.FormEvent) {
    ev.preventDefault(); setError("");
    const n = (v: any) => (v === "" || v === null || v === undefined ? null : Number(v));
    const cuerpo = { ...f, numero: f.numero || null, entidad: f.entidad || null, tribunal: f.tribunal || null, notas: f.notas || null,
      calendario_id: n(f.calendario_id), responsable_id: n(f.responsable_id), expediente_id: n(f.expediente_id), ev_asunto_id: n(f.ev_asunto_id),
      cr_cliente_id: cliente?.id ?? null };
    try { onGuardado(inicial?.id ? await api.patch(`/agenda/asuntos/${inicial.id}`, cuerpo) : await api.post("/agenda/asuntos", cuerpo)); }
    catch (e: any) { setError(e.message); }
  }
  return (
    <Modal titulo={inicial?.id ? "Editar asunto" : "Nuevo asunto"} onCerrar={onCerrar} ancho="max-w-2xl">
      <form onSubmit={guardar} className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><SelectorCliente valor={cliente} onCambio={(c) => { setCliente(c); if (c && !f.titulo) setF({ ...f, titulo: `${c.nombre} vs. ` }); }} etiqueta="Cliente (de su directorio)" /></div>
        <label className="sm:col-span-2"><span className="etiqueta">Nombre del asunto</span><input className="campo" required minLength={3} value={f.titulo} onChange={set("titulo")} placeholder="Ej. Pérez vs. Empresa X" /></label>
        <label><span className="etiqueta">Número de expediente o juicio</span><input className="campo" value={f.numero || ""} onChange={set("numero")} placeholder="Ej. 1450/2026" /></label>
        <label><span className="etiqueta">Materia</span><select className="campo" required value={f.materia} onChange={set("materia")}><option value="">Elija…</option>{Object.entries(cat.materias).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label><span className="etiqueta">Jurisdicción</span><select className="campo" value={f.jurisdiccion} onChange={set("jurisdiccion")}>{Object.entries(cat.jurisdicciones).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        {f.jurisdiccion === "estatal" ? <label><span className="etiqueta">Entidad</span><select className="campo" required value={f.entidad || ""} onChange={set("entidad")}><option value="">Elija…</option>{cat.entidades.map((x: string) => <option key={x}>{x}</option>)}</select></label> : <span />}
        <label className="sm:col-span-2"><span className="etiqueta">Tribunal o autoridad</span><input className="campo" value={f.tribunal || ""} onChange={set("tribunal")} placeholder="Ej. Juzgado Tercero de Distrito en Materia Administrativa" /></label>
        <label><span className="etiqueta">Calendario de días hábiles</span><select className="campo" value={f.calendario_id ?? ""} onChange={set("calendario_id")}><option value="">Sin calendario (solo fines de semana y art. 74 LFT)</option>{cat.calendarios.map((c: any) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Responsable</span><select className="campo" value={f.responsable_id ?? ""} onChange={set("responsable_id")}><option value="">Sin asignar</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
        {cat.vinculos.ev_asuntos && <label><span className="etiqueta">Vincular con Evidencia (opcional)</span><select className="campo" value={f.ev_asunto_id ?? ""} onChange={set("ev_asunto_id")}><option value="">Sin vincular</option>{cat.vinculos.ev_asuntos.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>}
        {cat.vinculos.expedientes && <label><span className="etiqueta">Vincular con expediente de nómina (opcional)</span><select className="campo" value={f.expediente_id ?? ""} onChange={set("expediente_id")}><option value="">Sin vincular</option>{cat.vinculos.expedientes.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>}
        <label className="sm:col-span-2"><span className="etiqueta">Notas internas</span><textarea className="campo" rows={2} value={f.notas || ""} onChange={set("notas")} /></label>
        <div className="sm:col-span-2"><Aviso>{error}</Aviso></div>
        <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}
