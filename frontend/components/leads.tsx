"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha } from "@/lib/api";

/** Marco de Nomira Leads: submenú del módulo. */
export function LeadsShell({ children }: { children: React.ReactNode }) {
  const ruta = usePathname();
  const enlaces: [string, string, boolean][] = [
    ["/leads", "Bandeja", ruta === "/leads"], ["/leads/prospectos", "Prospectos", ruta.startsWith("/leads/prospectos")],
    ["/leads/tablero", "Seguimiento", ruta.startsWith("/leads/tablero")], ["/leads/campanas", "Campañas y fuentes", ruta.startsWith("/leads/campanas")],
    ["/leads/reportes", "Resultados", ruta.startsWith("/leads/reportes")], ["/leads/configuracion", "Configuración", ruta.startsWith("/leads/configuracion")],
  ];
  return (
    <Shell>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-turquesa-700">Nomira Leads</p>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-crema-300" aria-label="Nomira Leads">
        {enlaces.map(([href, t, activo]) => (
          <Link key={href} href={href} aria-current={activo ? "page" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${activo ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>{t}</Link>
        ))}
      </nav>
      {children}
      <p className="mt-10 text-center text-xs text-slate-400">Nomira organiza la atención de prospectos. No da asesoría jurídica ni promete resultados: el abogado evalúa cada caso.</p>
    </Shell>
  );
}

let cache: any = null;
const avisos = new Set<(c: any) => void>();
/** Catálogos del módulo: etapas, canales, usuarios, campañas, permisos. */
export function useCatalogosLeads(): any {
  const [c, setC] = useState<any>(cache);
  useEffect(() => {
    avisos.add(setC);
    if (!cache) recargarCatalogosLeads();
    return () => { avisos.delete(setC); };
  }, []);
  return c;
}
export function recargarCatalogosLeads() {
  return api.get("/leads/catalogos").then((x) => { cache = x; avisos.forEach((f) => f(x)); return x; }).catch(() => null);
}

export function Etiqueta({ clase = "bg-slate-100 text-slate-700", children }: { clase?: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${clase}`}>{children}</span>;
}

export const COLOR_ETAPA: Record<string, string> = { abierta: "bg-turquesa-50 text-turquesa-700", ganada: "bg-emerald-100 text-emerald-800", perdida: "bg-slate-200 text-slate-600" };

export const hoyISO = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};
export const enDias = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

/** Teléfono legible: 525512345678 → +52 55 1234 5678 (si no es mexicano, se muestra tal cual). */
export function tel(t?: string | null): string {
  if (!t) return "—";
  if (t.startsWith("•")) return t;
  const m = /^52(\d{2})(\d{4})(\d{4})$/.exec(t);
  return m ? `+52 ${m[1]} ${m[2]} ${m[3]}` : `+${t}`;
}

/** «Próximo paso» en lenguaje sencillo: qué, cuándo y si ya venció. */
export function ProximoPaso({ p }: { p: any }) {
  if (!p) return <span className="font-semibold text-amber-700">Sin próximo paso</span>;
  return (
    <span className={p.vencida ? "font-semibold text-red-700" : p.hoy ? "font-semibold text-amber-700" : "text-slate-700"}>
      {p.tipo_texto}{p.descripcion ? `: ${p.descripcion}` : ""} · {p.vencida ? "venció el " : p.hoy ? "hoy" : ""}{p.hoy ? "" : fecha(p.fecha)}{p.hora ? ` ${p.hora}` : ""}
    </span>
  );
}

/** Fila de prospecto: quién es, qué necesita, quién lo atiende, siguiente paso y cuándo. */
export function FilaProspecto({ f }: { f: any }) {
  return (
    <Link href={`/leads/prospectos/${f.id}`} className="grid gap-1 px-4 py-3 text-sm hover:bg-crema/50 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1.2fr)] sm:gap-3">
      <span className="min-w-0">
        <b className="text-marino">{f.nombre}</b>
        {f.borrador && <Etiqueta clase="ml-2 bg-amber-100 text-amber-800">Borrador</Etiqueta>}
        {f.sin_responder > 0 && <Etiqueta clase="ml-2 bg-violet-100 text-violet-800">{f.sin_responder} sin responder</Etiqueta>}
        <span className="block truncate text-xs text-slate-500">{[f.materia, f.necesita].filter(Boolean).join(" · ") || "Sin descripción"}</span>
      </span>
      <span className="min-w-0 text-xs text-slate-600">
        <span className="block">{f.etapa} · {f.canal_texto}{f.campana ? ` · ${f.campana}` : ""}</span>
        <span className="block">Atiende: <b>{f.responsable || "sin asignar"}</b></span>
      </span>
      <span className="min-w-0 text-xs">{f.etapa_tipo === "abierta" ? <ProximoPaso p={f.proxima} />
        : f.etapa_tipo === "ganada" ? <span className="font-semibold text-emerald-700">Contratado</span> : <span className="text-slate-500">No contratado{f.motivo_perdida ? `: ${f.motivo_perdida}` : ""}</span>}</span>
    </Link>
  );
}

/** Alta rápida (menos de un minuto). Se puede guardar como borrador si faltan datos. */
export function AltaRapida({ onCerrar }: { onCerrar: () => void }) {
  const cat = useCatalogosLeads();
  const router = useRouter();
  const [d, setD] = useState<any>({ nombre: "", telefono: "", email: "", canal: "whatsapp", campana_id: "", materia: "", ciudad: "", descripcion: "",
    responsable_id: "", preferencia_contacto: "whatsapp", consentimiento: [] as string[], consentimiento_medio: "verbal",
    tipo: "llamada", fecha: hoyISO(), hora: "", paso: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const set = (k: string, v: any) => setD((x: any) => ({ ...x, [k]: v }));
  async function guardar(borrador: boolean) {
    setError(""); setEnviando(true);
    try {
      const r = await api.post("/leads/prospectos", {
        nombre: d.nombre, telefono: d.telefono || null, email: d.email || null, canal: d.canal, campana_id: d.campana_id ? Number(d.campana_id) : null,
        materia: d.materia || null, ciudad: d.ciudad || null, descripcion: d.descripcion || null, responsable_id: d.responsable_id ? Number(d.responsable_id) : null,
        preferencia_contacto: d.preferencia_contacto, consentimiento: d.consentimiento, consentimiento_medio: d.consentimiento_medio, borrador,
        proxima: d.fecha ? { tipo: d.tipo, fecha: d.fecha, hora: d.hora || null, descripcion: d.paso || null } : null,
      });
      router.push(`/leads/prospectos/${r.id}?nuevo=1`);
    } catch (e: any) { setError(e.message); setEnviando(false); }
  }
  if (!cat) return <Modal titulo="Agregar prospecto" onCerrar={onCerrar}><p className="text-sm text-slate-500">Cargando…</p></Modal>;
  return (
    <Modal titulo="Agregar prospecto" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); guardar(false); }}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="sm:col-span-2"><span className="etiqueta">Nombre</span>
            <input className="campo" autoFocus value={d.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre y apellido" /></label>
          <label><span className="etiqueta">Teléfono (WhatsApp)</span>
            <input className="campo" inputMode="tel" value={d.telefono} onChange={(e) => set("telefono", e.target.value)} placeholder="10 dígitos" /></label>
          <label><span className="etiqueta">Correo</span>
            <input className="campo" type="email" value={d.email} onChange={(e) => set("email", e.target.value)} /></label>
          <label><span className="etiqueta">¿Cómo llegó?</span>
            <select className="campo" value={d.canal} onChange={(e) => set("canal", e.target.value)}>
              {Object.entries(cat.canales).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
          <label><span className="etiqueta">Campaña (opcional)</span>
            <select className="campo" value={d.campana_id} onChange={(e) => set("campana_id", e.target.value)}>
              <option value="">Ninguna</option>
              {cat.campanas.filter((c: any) => c.activa).map((c: any) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Materia o servicio</span>
            <input className="campo" list="ld-materias" value={d.materia} onChange={(e) => set("materia", e.target.value)} />
            <datalist id="ld-materias">{cat.materias.map((x: string) => <option key={x} value={x} />)}</datalist></label>
          <label><span className="etiqueta">Ciudad (si aplica)</span>
            <input className="campo" value={d.ciudad} onChange={(e) => set("ciudad", e.target.value)} /></label>
          <label className="sm:col-span-2"><span className="etiqueta">¿Qué necesita? (breve)</span>
            <textarea className="campo" rows={2} maxLength={4000} value={d.descripcion} onChange={(e) => set("descripcion", e.target.value)}
              placeholder="Solo lo necesario para la primera atención. No pida documentos sensibles en este paso." /></label>
          <label><span className="etiqueta">Lo atiende</span>
            <select className="campo" value={d.responsable_id} onChange={(e) => set("responsable_id", e.target.value)}>
              <option value="">Yo</option>
              {cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Prefiere que le contacten por</span>
            <select className="campo" value={d.preferencia_contacto} onChange={(e) => set("preferencia_contacto", e.target.value)}>
              {Object.entries(cat.preferencias).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        </div>
        <fieldset className="rounded-xl border border-crema-300 p-3">
          <legend className="etiqueta px-1">Autorizó que le contacten por</legend>
          <div className="flex flex-wrap gap-4 text-sm">
            {Object.entries(cat.canales_consentimiento).map(([k, t]: any) => (
              <label key={k} className="flex items-center gap-1.5"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.consentimiento.includes(k)}
                onChange={(e) => set("consentimiento", e.target.checked ? [...d.consentimiento, k] : d.consentimiento.filter((x: string) => x !== k))} />{t}</label>))}
            <select className="campo w-auto py-1 text-xs" value={d.consentimiento_medio} onChange={(e) => set("consentimiento_medio", e.target.value)} aria-label="Cómo lo autorizó">
              {["verbal", "escrito", "mensaje"].map((k) => <option key={k} value={k}>{cat.medios_consentimiento[k]}</option>)}</select>
          </div>
          <p className="mt-1 text-xs text-slate-500">Finalidad: {cat.finalidad}.</p>
        </fieldset>
        <fieldset className="rounded-xl border border-turquesa/40 bg-turquesa-50/40 p-3">
          <legend className="etiqueta px-1">Próximo paso</legend>
          <div className="grid gap-2 sm:grid-cols-[auto_auto_auto_1fr]">
            <select className="campo" value={d.tipo} onChange={(e) => set("tipo", e.target.value)} aria-label="Tipo de próximo paso">
              {Object.entries(cat.tipos_accion).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select>
            <input className="campo" type="date" value={d.fecha} onChange={(e) => set("fecha", e.target.value)} aria-label="Fecha" />
            <input className="campo" type="time" value={d.hora} onChange={(e) => set("hora", e.target.value)} aria-label="Hora (opcional)" />
            <input className="campo" value={d.paso} maxLength={300} onChange={(e) => set("paso", e.target.value)} placeholder="Detalle (opcional)" />
          </div>
        </fieldset>
        <Aviso>{error}</Aviso>
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="btn-sec" disabled={enviando || !d.nombre.trim()} onClick={() => guardar(true)}>Guardar como borrador</button>
          <button type="submit" className="btn-turquesa" disabled={enviando}>{enviando ? "Guardando…" : "Agregar prospecto"}</button>
        </div>
      </form>
    </Modal>
  );
}

/** Copia un texto y avisa. */
export function Copiar({ texto, etiqueta = "Copiar" }: { texto: string; etiqueta?: string }) {
  const [ok, setOk] = useState(false);
  return <button type="button" className="btn-sec px-2.5 py-1 text-xs" onClick={async () => {
    try { await navigator.clipboard.writeText(texto); setOk(true); setTimeout(() => setOk(false), 1800); } catch {}
  }}>{ok ? "¡Copiado!" : etiqueta}</button>;
}
