"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import ShellPlataforma from "@/components/plataforma";
import { Aviso, Modal } from "@/components/ui";
import { mxn } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

export const COLOR_ETAPA: Record<string, string> = {
  nuevo: "bg-sky-100 text-sky-800", contactado: "bg-indigo-100 text-indigo-800", demo: "bg-violet-100 text-violet-800",
  propuesta: "bg-amber-100 text-amber-800", negociacion: "bg-orange-100 text-orange-800", ganado: "bg-emerald-100 text-emerald-800", perdido: "bg-slate-200 text-slate-600",
};

export function Etapa({ etapa, texto }: { etapa: string; texto?: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${COLOR_ETAPA[etapa] || "bg-slate-100"}`}>{texto || etapa}</span>;
}

export function dinero(v: string | null | undefined) { return v ? mxn(v) : "—"; }
export function cuando(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-MX", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function useCatalogosVentas() {
  const [c, setC] = useState<any>(null);
  useEffect(() => { apiP.get("/ventas/catalogos").then(setC).catch(() => {}); }, []);
  return c;
}

export function VentasShell({ children, acciones }: { children: React.ReactNode; acciones?: React.ReactNode }) {
  const ruta = usePathname();
  const tabs: [string, string, boolean][] = [
    ["/plataforma/ventas", "Embudo", ruta === "/plataforma/ventas" || ruta.startsWith("/plataforma/ventas/oportunidades")],
    ["/plataforma/ventas/tareas", "Mis tareas", ruta.startsWith("/plataforma/ventas/tareas")],
    ["/plataforma/ventas/contactos", "Contactos", ruta.startsWith("/plataforma/ventas/contactos")],
    ["/plataforma/ventas/campanas", "Campañas", ruta.startsWith("/plataforma/ventas/campanas")],
    ["/plataforma/comercial/cotizaciones", "Cotizaciones", false],
  ];
  return (
    <ShellPlataforma>
      <div className="mb-1 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">Ventas de Nomira</p>
          <h1 className="text-3xl font-extrabold text-marino">CRM</h1></div>
        <div className="flex flex-wrap gap-2">{acciones}</div>
      </div>
      <nav className="mb-6 mt-3 flex gap-1 overflow-x-auto border-b border-crema-300" aria-label="Ventas">
        {tabs.map(([href, t, activo]) => (
          <Link key={href} href={href} aria-current={activo ? "page" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${activo ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>{t}</Link>))}
      </nav>
      {children}
    </ShellPlataforma>
  );
}

const VACIO_CT = { nombre: "", despacho: "", cargo: "", email: "", telefono: "", ciudad: "", entidad: "", abogados: "", especialidad: "", origen: "otro", campana_id: "", propietario_id: "", notas: "", etiquetas: "", no_contactar: false };

function cuerpoContacto(f: any) {
  const n = (v: any) => (v === "" || v === null || v === undefined ? null : v);
  return { ...f, despacho: n(f.despacho), cargo: n(f.cargo), email: n(f.email), telefono: n(f.telefono), ciudad: n(f.ciudad), entidad: n(f.entidad),
    especialidad: n(f.especialidad), notas: n(f.notas), abogados: f.abogados ? Number(f.abogados) : null, campana_id: f.campana_id ? Number(f.campana_id) : null,
    propietario_id: f.propietario_id ? Number(f.propietario_id) : null, etiquetas: String(f.etiquetas || "").split(",").map((t: string) => t.trim()).filter(Boolean) };
}

function CamposContacto({ f, setF, cat }: { f: any; setF: (x: any) => void; cat: any }) {
  const c = (k: string) => ({ value: f[k] ?? "", onChange: (e: any) => setF({ ...f, [k]: e.target.value }) });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label><span className="etiqueta">Nombre de la persona</span><input className="campo" required minLength={2} {...c("nombre")} /></label>
      <label><span className="etiqueta">Despacho o empresa</span><input className="campo" {...c("despacho")} /></label>
      <label><span className="etiqueta">Correo</span><input className="campo" type="email" {...c("email")} /></label>
      <label><span className="etiqueta">Teléfono / WhatsApp</span><input className="campo" {...c("telefono")} /></label>
      <label><span className="etiqueta">Cargo</span><input className="campo" placeholder="Socio, director…" {...c("cargo")} /></label>
      <label><span className="etiqueta">Ciudad</span><input className="campo" {...c("ciudad")} /></label>
      <label><span className="etiqueta">Abogados en el despacho</span><input className="campo" type="number" min={1} {...c("abogados")} /></label>
      <label><span className="etiqueta">Especialidad</span><input className="campo" placeholder="Laboral, administrativo…" {...c("especialidad")} /></label>
      <label><span className="etiqueta">¿Cómo llegó?</span><select className="campo" {...c("origen")}>{Object.entries(cat.origenes).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
      <label><span className="etiqueta">Campaña</span><select className="campo" {...c("campana_id")}><option value="">Ninguna</option>{cat.campanas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
    </div>
  );
}

/** Nueva oportunidad: con un contacto existente o capturándolo en el momento. */
export function FormOportunidad({ cat, contacto, onCerrar, onListo }: { cat: any; contacto?: any; onCerrar: () => void; onListo: (o: any) => void }) {
  const [ct, setCt] = useState<any>({ ...VACIO_CT });
  const [f, setF] = useState<any>({ titulo: "", etapa: "nuevo", valor_mensual: "", paquete_interes: "", cierre_estimado: "", propietario_id: String(cat.yo), campana_id: "" });
  const [error, setError] = useState("");
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      onListo(await apiP.post("/ventas/oportunidades", { ...f, valor_mensual: f.valor_mensual || null, paquete_interes: f.paquete_interes || null, cierre_estimado: f.cierre_estimado || null,
        propietario_id: f.propietario_id ? Number(f.propietario_id) : null, campana_id: f.campana_id ? Number(f.campana_id) : null,
        ...(contacto ? { contacto_id: contacto.id } : { contacto: cuerpoContacto(ct) }) }));
    } catch (x: any) { setError(x.message); }
  }
  const c = (k: string) => ({ value: f[k] ?? "", onChange: (e: any) => setF({ ...f, [k]: e.target.value }) });
  return (
    <Modal titulo="Nueva oportunidad" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-4" onSubmit={guardar}>
        {contacto ? <p className="text-sm">Contacto: <b>{contacto.nombre}</b>{contacto.despacho ? ` · ${contacto.despacho}` : ""}</p>
          : <fieldset className="rounded-xl border border-crema-300 p-3"><legend className="etiqueta px-1">Contacto</legend><CamposContacto f={ct} setF={setCt} cat={cat} /></fieldset>}
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="sm:col-span-2"><span className="etiqueta">Nombre de la oportunidad</span><input className="campo" required minLength={2} placeholder="Ej. Bufete Pérez · plan Medio con Agenda" {...c("titulo")} /></label>
          <label><span className="etiqueta">Etapa</span><select className="campo" {...c("etapa")}>{cat.etapas.filter((x: any) => cat.abiertas.includes(x.clave)).map((x: any) => <option key={x.clave} value={x.clave}>{x.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Valor mensual estimado (sin IVA)</span><input className="campo" inputMode="decimal" placeholder="0.00" value={f.valor_mensual} onChange={(e) => setF({ ...f, valor_mensual: e.target.value.replace(/[^\d.]/g, "") })} /></label>
          <label><span className="etiqueta">Paquete de interés</span><select className="campo" {...c("paquete_interes")}><option value="">Sin definir</option>{cat.paquetes.map((p: string) => <option key={p}>{p}</option>)}</select></label>
          <label><span className="etiqueta">Cierre estimado</span><input className="campo" type="date" {...c("cierre_estimado")} /></label>
          <label><span className="etiqueta">Responsable</span><select className="campo" {...c("propietario_id")}>{cat.equipo.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Campaña</span><select className="campo" {...c("campana_id")}><option value="">La del contacto</option>{cat.campanas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
        </div>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Crear oportunidad</button></div>
      </form>
    </Modal>
  );
}

export function FormContacto({ cat, contacto, onCerrar, onListo }: { cat: any; contacto?: any; onCerrar: () => void; onListo: (c: any) => void }) {
  const [f, setF] = useState<any>(() => contacto ? { ...VACIO_CT, ...Object.fromEntries(Object.entries(contacto).map(([k, v]) => [k, v ?? ""])), etiquetas: (contacto.etiquetas || []).join(", ") } : { ...VACIO_CT, propietario_id: String(cat.yo) });
  const [error, setError] = useState("");
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { onListo(contacto ? await apiP.put(`/ventas/contactos/${contacto.id}`, cuerpoContacto(f)) : await apiP.post("/ventas/contactos", cuerpoContacto(f))); }
    catch (x: any) { setError(x.message); }
  }
  return (
    <Modal titulo={contacto ? "Editar contacto" : "Nuevo contacto"} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-3" onSubmit={guardar}>
        <CamposContacto f={f} setF={setF} cat={cat} />
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Responsable</span><select className="campo" value={f.propietario_id ?? ""} onChange={(e) => setF({ ...f, propietario_id: e.target.value })}><option value="">Sin asignar</option>{cat.equipo.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Etiquetas (separadas por coma)</span><input className="campo" value={f.etiquetas} onChange={(e) => setF({ ...f, etiquetas: e.target.value })} /></label>
        </div>
        <label className="block"><span className="etiqueta">Notas</span><textarea className="campo" rows={2} value={f.notas} onChange={(e) => setF({ ...f, notas: e.target.value })} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.no_contactar} onChange={(e) => setF({ ...f, no_contactar: e.target.checked })} /> Pidió no ser contactado (no se le registrarán llamadas, correos ni WhatsApp)</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

/** Registrar lo que pasó (llamada, correo, reunión, nota) o programar una tarea con fecha. */
export function FormActividad({ cat, oportunidadId, contactoId, onCerrar, onListo, tarea = false }: { cat: any; oportunidadId?: number; contactoId?: number; onCerrar: () => void; onListo: () => void; tarea?: boolean }) {
  const manana = (() => { const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(10, 0, 0, 0); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); })();
  const [f, setF] = useState<any>({ tipo: tarea ? "tarea" : "llamada", titulo: "", detalle: "", programar: tarea, vence_en: manana, asignado_id: String(cat.yo) });
  const [error, setError] = useState("");
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await apiP.post("/ventas/actividades", { oportunidad_id: oportunidadId ?? null, contacto_id: contactoId ?? null, tipo: f.tipo, titulo: f.titulo, detalle: f.detalle || null,
        vence_en: f.programar ? new Date(f.vence_en).toISOString() : null, asignado_id: f.programar && f.asignado_id ? Number(f.asignado_id) : null });
      onListo();
    } catch (x: any) { setError(x.message); }
  }
  return (
    <Modal titulo={f.programar ? "Programar tarea" : "Registrar actividad"} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={guardar}>
        <div className="flex gap-4 text-sm"><label className="flex items-center gap-2"><input type="radio" checked={!f.programar} onChange={() => setF({ ...f, programar: false })} /> Ya pasó</label>
          <label className="flex items-center gap-2"><input type="radio" checked={f.programar} onChange={() => setF({ ...f, programar: true })} /> Por hacer (tarea)</label></div>
        <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
          <label><span className="etiqueta">Tipo</span><select className="campo" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>
            {Object.entries(cat.tipos).filter(([k]) => k !== "sistema").map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
          <label><span className="etiqueta">{f.programar ? "Qué hay que hacer" : "Qué pasó"}</span><input className="campo" required minLength={2} placeholder={f.programar ? "Ej. Llamar para agendar demo" : "Ej. Llamada: le interesa Agenda"} value={f.titulo} onChange={(e) => setF({ ...f, titulo: e.target.value })} /></label>
        </div>
        {f.programar && <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Fecha y hora</span><input className="campo" type="datetime-local" required value={f.vence_en} onChange={(e) => setF({ ...f, vence_en: e.target.value })} /></label>
          <label><span className="etiqueta">Para</span><select className="campo" value={f.asignado_id} onChange={(e) => setF({ ...f, asignado_id: e.target.value })}>{cat.equipo.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
        </div>}
        <label className="block"><span className="etiqueta">Detalle (opcional)</span><textarea className="campo" rows={3} value={f.detalle} onChange={(e) => setF({ ...f, detalle: e.target.value })} /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

export function Historial({ actividades, onCambio }: { actividades: any[]; onCambio: () => void }) {
  const [error, setError] = useState("");
  const [cerrar, setCerrar] = useState<any>(null);
  const pendientes = actividades.filter((a) => a.es_tarea && !a.completada_en);
  const pasado = actividades.filter((a) => !(a.es_tarea && !a.completada_en));
  return (
    <div>
      <Aviso>{error}</Aviso>
      {pendientes.length > 0 && <ul className="mb-3 space-y-2">{pendientes.map((a) => {
        const vencida = new Date(a.vence_en) < new Date();
        return <li key={a.id} className={`flex items-start justify-between gap-2 rounded-xl border p-3 text-sm ${vencida ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
          <span><b>{a.tipo_texto}: {a.titulo}</b><span className={`block text-xs ${vencida ? "text-red-700" : "text-slate-600"}`}>{vencida ? "Venció" : "Para"} {cuando(a.vence_en)}{a.asignado ? ` · ${a.asignado}` : ""}</span></span>
          <button className="btn-sec whitespace-nowrap text-xs" onClick={() => setCerrar(a)}>✓ Hecho</button></li>;
      })}</ul>}
      <ol className="relative space-y-3 border-l border-crema-300 pl-4">{pasado.map((a) => (
        <li key={a.id} className="text-sm"><span className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ${a.tipo === "sistema" ? "bg-slate-300" : "bg-turquesa"}`} />
          <p className={a.tipo === "sistema" ? "text-slate-500" : "font-semibold text-marino"}>{a.tipo !== "sistema" && `${a.tipo_texto}: `}{a.titulo}</p>
          {a.detalle && <p className="whitespace-pre-line text-slate-700">{a.detalle}</p>}
          {a.resultado && <p className="text-slate-600">Resultado: {a.resultado}</p>}
          <p className="text-xs text-slate-400">{cuando(a.completada_en || a.creado_en)}{a.creado_por ? ` · ${a.creado_por}` : ""}</p></li>))}
        {!pasado.length && <li className="text-sm text-slate-500">Sin actividad todavía.</li>}</ol>
      {cerrar && <CompletarTarea tarea={cerrar} onCerrar={() => setCerrar(null)} onListo={() => { setCerrar(null); onCambio(); }} />}
    </div>
  );
}

export function CompletarTarea({ tarea, onCerrar, onListo }: { tarea: any; onCerrar: () => void; onListo: () => void }) {
  const [resultado, setResultado] = useState("");
  const [error, setError] = useState("");
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { await apiP.post(`/ventas/actividades/${tarea.id}/completar`, { resultado: resultado || null }); onListo(); } catch (x: any) { setError(x.message); }
  }
  return (
    <Modal titulo={`Hecho: ${tarea.titulo}`} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={guardar}>
        <label className="block"><span className="etiqueta">¿Cómo salió? (opcional)</span><input className="campo" autoFocus value={resultado} onChange={(e) => setResultado(e.target.value)} placeholder="Ej. Agendamos demo para el jueves" /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Marcar como hecha</button></div>
      </form>
    </Modal>
  );
}
