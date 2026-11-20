"use client";
import { useCallback, useEffect, useState } from "react";
import { TextoLegal } from "@/components/legal";
import ShellPlataforma from "@/components/plataforma";
import { Aviso, Modal } from "@/components/ui";
import { fecha, fechaHora } from "@/lib/api";
import { apiP, avisarContadores } from "@/lib/plataforma";

const COLOR: Record<string, string> = { borrador: "bg-amber-100 text-amber-800", publicada: "bg-emerald-100 text-emerald-800", retirada: "bg-slate-200 text-slate-600" };
const ACEPTABLES = ["terminos", "privacidad", "anexo_tratamiento"];

/** Centro Legal en el panel: publicar versiones APROBADAS (sin modificarlas), contacto de privacidad,
 *  solicitudes ARCO y evidencia de aceptación. */
export default function Legal() {
  const [vista, setVista] = useState("documentos");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const hacer = async (fn: () => Promise<any>, exito: string) => {
    setError(""); setOk("");
    try { const r = await fn(); setOk(exito); avisarContadores(); return r || true; } catch (e: any) { setError(e.message); return null; }
  };
  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Centro legal</h1>
      <p className="mt-1 text-sm text-slate-500">Publique solo textos ya revisados y aprobados por el responsable de Nomira y su abogado. Nomira no redacta ni resume documentos legales.</p>
      <div className="my-4 flex flex-wrap gap-2 text-sm">
        {[["documentos", "Documentos"], ["arco", "Solicitudes ARCO"], ["contacto", "Contacto de privacidad"], ["evidencia", "Evidencia de aceptación"]].map(([k, t]) => (
          <button key={k} onClick={() => setVista(k)} className={`rounded-full px-3 py-1.5 font-semibold ${vista === k ? "bg-marino text-white" : "bg-crema-200 text-marino"}`}>{t}</button>))}
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {vista === "documentos" && <Documentos hacer={hacer} />}
      {vista === "arco" && <Arco hacer={hacer} />}
      {vista === "contacto" && <Contacto hacer={hacer} />}
      {vista === "evidencia" && <Evidencia />}
    </ShellPlataforma>
  );
}

function Documentos({ hacer }: any) {
  const [docs, setDocs] = useState<any[] | null>(null);
  const [nueva, setNueva] = useState<any>(null);
  const [ver, setVer] = useState<any>(null);
  const [publicar, setPublicar] = useState<any>(null);
  const cargar = useCallback(() => apiP.get("/legal/documentos").then(setDocs).catch(() => setDocs([])), []);
  useEffect(() => { cargar(); }, [cargar]);
  if (!docs) return <p className="text-sm text-slate-500">Cargando…</p>;
  return (
    <div className="space-y-4">
      {docs.map((d) => (
        <section key={d.clave} className="tarjeta p-5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><h2 className="font-bold text-marino">{d.titulo}</h2><p className="text-xs text-slate-500">{d.descripcion}
              {d.evento === "aceptacion" && (d.quien === "organizacion" ? " · Lo acepta el administrador de cada despacho." : " · Cada usuario lo acepta al entrar.")}
              {d.evento === "lectura" && " · Cada usuario confirma haberlo leído."}</p></div>
            <button className="btn-sec text-xs" onClick={() => setNueva({ documento: d.clave, titulo: d.titulo, version: "", contenido: "", resumen_cambios: "", requiere_aceptacion: false, vigente_desde: "" })}>+ Nueva versión</button>
          </div>
          {d.versiones.length === 0 ? <p className="mt-2 text-sm text-amber-700">Sin versiones: el sitio lo muestra «en preparación».</p> : (
            <ul className="mt-3 divide-y divide-crema-200 text-sm">
              {d.versiones.map((v: any) => (
                <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span><b>v{v.version}</b> <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-semibold ${COLOR[v.estado]}`}>{v.estado}{d.vigente_id === v.id ? " · vigente" : ""}</span>
                    <span className="block text-xs text-slate-500">{v.publicado_en ? `Publicada ${fechaHora(v.publicado_en)} por ${v.publicado_por || "—"} · Aprobada por: ${v.aprobado_por}` : `Borrador creado ${fechaHora(v.creado_en)}`}
                      {v.requiere_aceptacion ? " · pide nueva aceptación" : ""} · {v.eventos} registro(s) de aceptación</span></span>
                  <span className="flex gap-2">
                    <button className="btn-sec px-2 py-1 text-xs" onClick={() => setVer(v)}>Ver</button>
                    {v.estado === "borrador" && <>
                      <button className="btn-sec px-2 py-1 text-xs" onClick={() => setNueva({ ...v, vigente_desde: v.vigente_desde || "", resumen_cambios: v.resumen_cambios || "" })}>Editar</button>
                      <button className="btn-turquesa px-2 py-1 text-xs" onClick={() => setPublicar(v)}>Publicar</button>
                      <button className="btn-peligro px-2 py-1 text-xs" onClick={() => hacer(() => apiP.borrar(`/legal/versiones/${v.id}`), "Borrador eliminado.").then(cargar)}>Borrar</button></>}
                    {v.estado === "publicada" && <button className="btn-peligro px-2 py-1 text-xs" onClick={() => {
                      if (confirm("¿Retirar esta versión? Dejará de mostrarse como vigente; queda en el historial.")) hacer(() => apiP.post(`/legal/versiones/${v.id}/retirar`), "Versión retirada.").then(cargar);
                    }}>Retirar</button>}
                  </span>
                </li>))}
            </ul>)}
        </section>))}
      {nueva && <EditorVersion v={nueva} onCerrar={() => setNueva(null)} hacer={hacer} onListo={() => { setNueva(null); cargar(); }} />}
      {ver && <Modal titulo={`${ver.titulo} · v${ver.version}`} onCerrar={() => setVer(null)} ancho="max-w-3xl">
        <div className="max-h-[70vh] overflow-y-auto"><TextoLegal texto={ver.contenido} /></div>
        {ver.sha256 && <p className="mt-3 break-all text-[11px] text-slate-400">SHA-256: {ver.sha256}</p>}
      </Modal>}
      {publicar && <ModalPublicar v={publicar} onCerrar={() => setPublicar(null)} hacer={hacer} onListo={() => { setPublicar(null); cargar(); }} />}
    </div>
  );
}

function EditorVersion({ v, onCerrar, hacer, onListo }: any) {
  const [d, setD] = useState<any>(v);
  const [previa, setPrevia] = useState(false);
  const editar = !!v.id;
  return (
    <Modal titulo={editar ? `Editar borrador · ${v.titulo}` : `Nueva versión · ${v.titulo}`} onCerrar={onCerrar} ancho="max-w-4xl">
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        const cuerpo = { version: d.version, titulo: d.titulo || null, contenido: d.contenido, resumen_cambios: d.resumen_cambios || null,
          requiere_aceptacion: d.requiere_aceptacion, vigente_desde: d.vigente_desde || null };
        const r = await hacer(() => editar ? apiP.patch(`/legal/versiones/${v.id}`, cuerpo) : apiP.post("/legal/versiones", { documento: v.documento, ...cuerpo }), "Borrador guardado. Revíselo y publíquelo cuando esté listo.");
        if (r) onListo();
      }}>
        <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-900">Pegue el texto <b>exactamente como fue aprobado</b>. Puede usar formato sencillo: «# Título», «## Subtítulo», listas con «-» o «1.», **negritas** y enlaces [texto](https://…).</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <label><span className="etiqueta">Versión</span><input className="campo" required placeholder="1.0" value={d.version} onChange={(e) => setD({ ...d, version: e.target.value })} /></label>
          <label><span className="etiqueta">Vigente desde (opcional)</span><input className="campo" type="date" value={d.vigente_desde} onChange={(e) => setD({ ...d, vigente_desde: e.target.value })} /></label>
          <label><span className="etiqueta">Título visible</span><input className="campo" value={d.titulo} onChange={(e) => setD({ ...d, titulo: e.target.value })} /></label>
        </div>
        <div className="flex gap-2 text-sm"><button type="button" onClick={() => setPrevia(false)} className={`rounded-full px-3 py-1 font-semibold ${!previa ? "bg-marino text-white" : "bg-crema-200"}`}>Texto</button>
          <button type="button" onClick={() => setPrevia(true)} className={`rounded-full px-3 py-1 font-semibold ${previa ? "bg-marino text-white" : "bg-crema-200"}`}>Vista previa</button></div>
        {previa ? <div className="max-h-[50vh] overflow-y-auto rounded-xl border border-crema-300 p-4"><TextoLegal texto={d.contenido || "(vacío)"} /></div>
          : <textarea className="campo font-mono text-xs" rows={18} required minLength={20} value={d.contenido} onChange={(e) => setD({ ...d, contenido: e.target.value })} />}
        <label className="block"><span className="etiqueta">Resumen de cambios (se muestra en el historial)</span><input className="campo" maxLength={1000} value={d.resumen_cambios} onChange={(e) => setD({ ...d, resumen_cambios: e.target.value })} /></label>
        {ACEPTABLES.includes(v.documento) && <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={d.requiere_aceptacion} onChange={(e) => setD({ ...d, requiere_aceptacion: e.target.checked })} />
          <span>Pedir nueva aceptación a quien ya aceptó una versión anterior <span className="text-slate-500">(márquelo solo si el cambio y su política lo requieren; la primera publicación siempre se pide)</span></span></label>}
        <div className="flex justify-end"><button className="btn-turquesa">Guardar borrador</button></div>
      </form>
    </Modal>
  );
}

function ModalPublicar({ v, onCerrar, hacer, onListo }: any) {
  const [confirmo, setConfirmo] = useState(false);
  const [aprobado, setAprobado] = useState("");
  return (
    <Modal titulo={`Publicar ${v.titulo} v${v.version}`} onCerrar={onCerrar}>
      <div className="space-y-3 text-sm">
        <p>Al publicarla se vuelve la versión vigente y <b>ya no se podrá modificar</b> (un cambio será una versión nueva). Se guarda su huella SHA-256.</p>
        <label className="block"><span className="etiqueta">Aprobado por</span><input className="campo" placeholder="Ej. Nombre del responsable de Nomira y Lic. Nombre del abogado" value={aprobado} onChange={(e) => setAprobado(e.target.value)} /></label>
        <label className="flex items-start gap-2"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} />
          <span>Confirmo que este texto fue revisado y aprobado por el responsable de Nomira y su abogado, y que se publica sin cambios.</span></label>
        <div className="flex justify-end"><button className="btn-turquesa" disabled={!confirmo || aprobado.trim().length < 3}
          onClick={async () => { if (await hacer(() => apiP.post(`/legal/versiones/${v.id}/publicar`, { confirmo_aprobacion: confirmo, aprobado_por: aprobado }), "Versión publicada.")) onListo(); }}>Publicar</button></div>
      </div>
    </Modal>
  );
}

function Arco({ hacer }: any) {
  const [r, setR] = useState<any>(null);
  const [abierta, setAbierta] = useState<number | null>(null);
  const [cambio, setCambio] = useState<any>({ estado: "en_revision", nota: "" });
  const cargar = useCallback(() => apiP.get("/legal/arco").then(setR).catch(() => setR({ solicitudes: [], estados: {} })), []);
  useEffect(() => { cargar(); }, [cargar]);
  if (!r) return <p className="text-sm text-slate-500">Cargando…</p>;
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">La fecha «responder antes de» es una referencia de 20 días hábiles (no descuenta días festivos). Ninguna solicitud se marca atendida sola: registre qué se respondió y por qué medio.</p>
      {r.solicitudes.length === 0 && <p className="tarjeta p-6 text-center text-sm text-slate-500">No hay solicitudes.</p>}
      {r.solicitudes.map((s: any) => (
        <article key={s.id} className={`tarjeta p-4 text-sm ${s.vencida ? "border-red-300" : ""}`}>
          <button className="flex w-full flex-wrap items-center justify-between gap-2 text-left" onClick={() => { setAbierta(abierta === s.id ? null : s.id); setCambio({ estado: s.estado, nota: "" }); }}>
            <span><b className="font-mono">{s.folio}</b> · {s.tipo_texto} · {s.nombre}<span className="block text-xs text-slate-500">{s.relacion_texto}{s.despacho ? ` · ${s.despacho}` : ""} · recibida {fechaHora(s.recibida_en)}</span></span>
            <span className="text-xs"><span className="rounded-full bg-crema-200 px-2 py-0.5 font-semibold">{s.estado_texto}</span>
              {s.vence_en && !s.atendida_en && <span className={`ml-2 ${s.vencida ? "font-semibold text-red-700" : "text-slate-500"}`}>Responder antes de {fecha(s.vence_en)}</span>}</span>
          </button>
          {abierta === s.id && (
            <div className="mt-3 space-y-3 border-t border-crema-300 pt-3">
              <p><span className="text-slate-500">Correo:</span> {s.email}</p>
              <p className="whitespace-pre-line rounded-xl bg-crema/60 p-3">{s.descripcion}</p>
              <ol className="space-y-1 text-xs text-slate-600">{s.notas.map((n: any, i: number) => <li key={i}>{fechaHora(n.creado_en)} · <b>{n.estado_texto}</b>{n.admin ? ` (${n.admin})` : ""}{n.nota ? ` — ${n.nota}` : ""}</li>)}</ol>
              <div className="grid gap-2 sm:grid-cols-[auto_1fr_auto]">
                <select className="campo" value={cambio.estado} onChange={(e) => setCambio({ ...cambio, estado: e.target.value })}>
                  {Object.entries(r.estados).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select>
                <input className="campo" placeholder="Qué se hizo o respondió, y por qué medio" value={cambio.nota} onChange={(e) => setCambio({ ...cambio, nota: e.target.value })} />
                <button className="btn-turquesa" onClick={() => hacer(() => apiP.post(`/legal/arco/${s.id}`, cambio), "Solicitud actualizada.").then(cargar)}>Guardar</button>
              </div>
            </div>)}
        </article>))}
    </div>
  );
}

function Contacto({ hacer }: any) {
  const [c, setC] = useState<any>(null);
  useEffect(() => { apiP.get("/legal/config").then((x) => setC({ ...x, correo_privacidad: x.correo_privacidad || "", responsable_datos: x.responsable_datos || "" })).catch(() => {}); }, []);
  if (!c) return <p className="text-sm text-slate-500">Cargando…</p>;
  return (
    <form className="tarjeta max-w-2xl space-y-3 p-5" onSubmit={(e) => { e.preventDefault(); hacer(() => apiP.put("/legal/config", { ...c, correo_privacidad: c.correo_privacidad || null, responsable_datos: c.responsable_datos || null }), "Contacto guardado."); }}>
      <label className="block"><span className="etiqueta">Correo de privacidad (se muestra en el Centro legal)</span><input className="campo" type="email" value={c.correo_privacidad} onChange={(e) => setC({ ...c, correo_privacidad: e.target.value })} /></label>
      <label className="block"><span className="etiqueta">Persona o departamento de datos personales</span><input className="campo" value={c.responsable_datos} onChange={(e) => setC({ ...c, responsable_datos: e.target.value })} /></label>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={c.marketing_habilitado} onChange={(e) => setC({ ...c, marketing_habilitado: e.target.checked })} />
        <span>Pedir consentimiento opcional para información comercial <span className="text-slate-500">(actívelo solo si Nomira envía información comercial y su aviso de privacidad aprobado lo prevé)</span></span></label>
      <button className="btn-turquesa">Guardar</button>
    </form>
  );
}

function Evidencia() {
  const [filas, setFilas] = useState<any[] | null>(null);
  useEffect(() => { apiP.get("/legal/evidencia").then(setFilas).catch(() => setFilas([])); }, []);
  async function csv() {
    const t = await apiP.texto("/legal/evidencia?formato=csv");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([t], { type: "text/csv;charset=utf-8" }));
    a.download = "evidencia-legal.csv";
    a.click();
  }
  if (!filas) return <p className="text-sm text-slate-500">Cargando…</p>;
  return (
    <div>
      <div className="mb-3 flex items-center justify-between"><p className="text-xs text-slate-500">Últimos 500 registros. Solo se guarda usuario u organización, documento, versión, evento y fecha.</p>
        <button className="btn-sec" onClick={csv}>Descargar CSV</button></div>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla min-w-[760px]"><thead><tr><th>Fecha</th><th>Documento</th><th>Versión</th><th>Evento</th><th>Contexto</th><th>Organización</th><th>Usuario</th></tr></thead>
          <tbody>{filas.length === 0 ? <tr><td colSpan={7} className="text-center text-slate-400">Sin registros.</td></tr> : filas.map((f, i) => (
            <tr key={i}><td>{fechaHora(f.fecha)}</td><td>{f.documento}</td><td>{f.version || "—"}</td><td>{f.evento}</td><td>{f.contexto}</td><td>{f.organizacion || "—"}</td><td>{f.usuario || (f.solicitud_informes ? `Formulario #${f.solicitud_informes}` : "—")}</td></tr>))}</tbody></table>
      </div>
    </div>
  );
}
