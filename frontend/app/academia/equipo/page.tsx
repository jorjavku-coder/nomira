"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AcademiaShell, Barra, Insignia } from "@/components/academia";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha } from "@/lib/api";

const ESTADO: Record<string, string> = { completado: "bg-emerald-100 text-emerald-800", en_curso: "bg-turquesa-50 text-turquesa-700", sin_iniciar: "bg-slate-100 text-slate-600" };

/** Avance por persona, por curso y por equipo. Sin rankings: solo quién va y quién falta. */
export default function Equipo() {
  const [r, setR] = useState<any>(null);
  const [cursos, setCursos] = useState<any[]>([]);
  const [vista, setVista] = useState("persona");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [modal, setModal] = useState<any>(null);
  const cargar = () => api.get("/academia/equipo").then(setR).catch((e) => setError(e.message));
  useEffect(() => { cargar(); api.get("/academia/cursos").then((x) => setCursos(x.cursos)).catch(() => {}); }, []);
  async function hacer(fn: () => Promise<any>, exito: string) {
    setError(""); setOk("");
    try { await fn(); setOk(exito); await cargar(); return true; } catch (e: any) { setError(e.message); return false; }
  }
  if (!r) return <AcademiaShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AcademiaShell>;
  const titulos: Record<string, string> = Object.fromEntries(r.cursos.map((c: any) => [String(c.id), c.titulo]));
  return (
    <AcademiaShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Equipo</h1><p className="text-sm text-slate-500">Quién tiene cursos asignados, cómo va y quién ya terminó.</p></div>
        {r.es_admin && <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => api.descargar("/academia/reportes/excel", "academia-finalizacion.xlsx").catch((e) => setError(e.message))}>Descargar reporte</button>
          <button className="btn-turquesa" onClick={() => setModal({ tipo: "asignar" })}>Asignar curso</button>
        </div>}
      </div>
      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mb-4 flex gap-2 text-sm">
        {[["persona", "Por persona"], ["curso", "Por curso"], ["equipos", "Equipos"], ["historial", "Asignaciones"]].map(([k, t]) => (
          <button key={k} onClick={() => setVista(k)} className={`rounded-full px-3 py-1.5 font-semibold ${vista === k ? "bg-marino text-white" : "bg-crema-200 text-marino"}`}>{t}</button>))}
      </div>

      {vista === "persona" && (
        <div className="space-y-3">
          {r.personas.map((p: any) => (
            <details key={p.id} className="tarjeta p-4" open={r.personas.length <= 4}>
              <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2">
                <span><b className="text-marino">{p.nombre}</b>{!p.activo && <span className="ml-2 text-xs text-slate-400">(inactivo)</span>}
                  {p.equipos.length > 0 && <span className="block text-xs text-slate-500">{p.equipos.join(", ")}</span>}</span>
                <span className="text-xs text-slate-600">{p.completados} completado(s) de {Object.keys(p.cursos).length}{p.atrasados ? <b className="ml-2 text-red-700">{p.atrasados} con fecha vencida</b> : ""}</span>
              </summary>
              {Object.keys(p.cursos).length === 0 ? <p className="mt-2 text-sm text-slate-400">Sin cursos asignados ni iniciados.</p> : (
                <ul className="mt-3 divide-y divide-crema-200 text-sm">
                  {Object.entries(p.cursos).map(([cid, x]: any) => (
                    <li key={cid} className="grid gap-2 py-2 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto] sm:items-center">
                      <span>{titulos[cid] || "Curso"}{x.asignacion && <Insignia clase="ml-2 bg-crema-200 text-marino">{x.asignacion.tipo === "obligatorio" ? "Obligatorio" : "Recomendado"}{x.asignacion.por_equipo ? " · equipo" : ""}</Insignia>}
                        {x.asignacion?.fecha_sugerida && <span className={`block text-xs ${x.asignacion.vencida ? "font-semibold text-red-700" : "text-slate-500"}`}>Sugerido: {fecha(x.asignacion.fecha_sugerida)}</span>}</span>
                      <span><Barra valor={x.porcentaje} /><span className="text-xs text-slate-500">{x.texto}{x.calificacion !== null ? ` · calificación ${x.calificacion}` : ""}</span></span>
                      <span className="flex items-center gap-2"><Insignia clase={ESTADO[x.estado]}>{x.estado === "completado" ? `Completado ${fecha(x.completado_en)}` : x.estado === "en_curso" ? "En curso" : "Sin iniciar"}</Insignia>
                        {x.folio && r.es_admin && <button className="text-xs font-semibold text-turquesa-700 underline" onClick={() => api.descargar(`/academia/constancias/${x.avance_id}`, "constancia.pdf")}>Constancia</button>}</span>
                    </li>))}
                </ul>)}
            </details>))}
        </div>)}

      {vista === "curso" && (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full min-w-[620px] text-sm">
            <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
              <th className="px-4 py-2">Curso</th><th className="px-3 py-2 text-right">Asignados</th><th className="px-3 py-2 text-right">Iniciaron</th><th className="px-3 py-2 text-right">Completaron</th><th className="px-3 py-2 text-right">Fecha vencida</th></tr></thead>
            <tbody className="divide-y divide-crema-200">
              {r.por_curso.length === 0 && <tr><td colSpan={5} className="px-4 py-4 text-center text-slate-400">Aún no hay cursos asignados o iniciados.</td></tr>}
              {r.por_curso.map((c: any) => (
                <tr key={c.id}><td className="px-4 py-2"><Link className="font-semibold text-marino hover:underline" href={`/academia/cursos/${c.id}`}>{c.titulo}</Link>
                  <span className="block text-xs text-slate-500">{c.materia}{c.origen === "nomira" ? " · Nomira" : ""}{c.estado !== "publicado" ? ` · ${c.estado}` : ""}</span>
                  {c.aviso_vigencia && <span className="block text-xs text-amber-700">Revisar vigencia</span>}</td>
                  <td className="px-3 py-2 text-right">{c.asignados}</td><td className="px-3 py-2 text-right">{c.iniciados}</td><td className="px-3 py-2 text-right font-semibold">{c.completados}</td>
                  <td className={`px-3 py-2 text-right ${c.atrasados ? "font-semibold text-red-700" : ""}`}>{c.atrasados}</td></tr>))}
            </tbody>
          </table>
        </div>)}

      {vista === "equipos" && (
        <div className="space-y-3">
          {r.es_admin && <button className="btn-sec" onClick={() => setModal({ tipo: "equipo", e: null })}>+ Nuevo equipo</button>}
          {r.equipos.length === 0 && <p className="tarjeta p-5 text-sm text-slate-500">Agrupe a su personal (por ejemplo «Litigio» o «Recepción») para asignar cursos a todos a la vez. Quien se agregue después recibe los cursos del equipo.</p>}
          {r.equipos.map((e: any) => (
            <div key={e.id} className="tarjeta flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
              <span><b className="text-marino">{e.nombre}</b>{e.descripcion && <span className="text-slate-500"> · {e.descripcion}</span>}
                <span className="block text-xs text-slate-500">{e.miembros.map((x: any) => x.nombre).join(", ") || "Sin integrantes"}</span></span>
              <span className="w-48"><Barra valor={e.porcentaje ?? 0} /><span className="text-xs text-slate-500">{e.asignaciones ? `${e.completadas} de ${e.asignaciones} cursos asignados completados` : "Sin cursos asignados"}</span></span>
              {r.es_admin && <span className="flex gap-2"><button className="btn-sec text-xs" onClick={() => setModal({ tipo: "equipo", e })}>Editar</button>
                <button className="btn-peligro text-xs" onClick={() => hacer(() => api.borrar(`/academia/equipos/${e.id}`), "Equipo eliminado. Sus asignaciones quedaron en el historial.")}>Eliminar</button></span>}
            </div>))}
          {r.es_admin && <Instructores r={r} hacer={hacer} />}
        </div>)}

      {vista === "historial" && (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full min-w-[700px] text-sm">
            <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
              <th className="px-4 py-2">Curso</th><th className="px-3 py-2">Para</th><th className="px-3 py-2">Tipo</th><th className="px-3 py-2">Fecha sugerida</th><th className="px-3 py-2">Asignó</th><th className="px-3 py-2" /></tr></thead>
            <tbody className="divide-y divide-crema-200">
              {r.asignaciones.length === 0 && <tr><td colSpan={6} className="px-4 py-4 text-center text-slate-400">Sin asignaciones.</td></tr>}
              {r.asignaciones.map((a: any) => (
                <tr key={a.id} className={a.retirada_en ? "text-slate-400" : ""}><td className="px-4 py-2">{a.curso}</td><td className="px-3 py-2">{a.persona || (a.equipo ? `Equipo ${a.equipo}` : "—")}</td>
                  <td className="px-3 py-2">{a.tipo === "obligatorio" ? "Obligatorio" : "Recomendado"}</td><td className="px-3 py-2">{a.fecha_sugerida ? fecha(a.fecha_sugerida) : "—"}</td>
                  <td className="px-3 py-2">{a.asignado_por} · {fecha(a.creado_en)}</td>
                  <td className="px-3 py-2 text-right">{a.retirada_en ? `Retirada ${fecha(a.retirada_en)}` : r.es_admin && <button className="text-xs font-semibold text-red-700 hover:underline" onClick={() => hacer(() => api.borrar(`/academia/asignaciones/${a.id}`), "Asignación retirada. El avance de la persona se conserva.")}>Retirar</button>}</td></tr>))}
            </tbody>
          </table>
        </div>)}

      {modal?.tipo === "asignar" && <Asignar r={r} cursos={cursos} onCerrar={() => setModal(null)} hacer={hacer} />}
      {modal?.tipo === "equipo" && <EditarEquipo r={r} e={modal.e} onCerrar={() => setModal(null)} hacer={hacer} />}
    </AcademiaShell>
  );
}

function Personas({ r, valor, onCambio }: any) {
  return (
    <div className="grid max-h-56 gap-1 overflow-y-auto rounded-xl border border-crema-300 p-2 sm:grid-cols-2">
      {r.usuarios.filter((u: any) => u.activo).map((u: any) => (
        <label key={u.id} className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={valor.includes(u.id)}
          onChange={(e) => onCambio(e.target.checked ? [...valor, u.id] : valor.filter((x: number) => x !== u.id))} />{u.nombre}</label>))}
    </div>
  );
}

function Asignar({ r, cursos, onCerrar, hacer }: any) {
  const asignables = cursos.filter((c: any) => c.vigente);
  const [d, setD] = useState<any>({ curso_id: asignables[0]?.id ? String(asignables[0].id) : "", usuario_ids: [], equipo_ids: [], tipo: "obligatorio", fecha_sugerida: "" });
  return (
    <Modal titulo="Asignar curso" onCerrar={onCerrar} ancho="max-w-xl">
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        if (await hacer(() => api.post("/academia/asignaciones", { ...d, curso_id: Number(d.curso_id), fecha_sugerida: d.fecha_sugerida || null }), "Curso asignado.")) onCerrar();
      }}>
        <label className="block"><span className="etiqueta">Curso</span>
          <select className="campo" required value={d.curso_id} onChange={(e) => setD({ ...d, curso_id: e.target.value })}>
            {asignables.map((c: any) => <option key={c.id} value={c.id}>{c.titulo}{c.origen === "nomira" ? " (Nomira)" : ""}</option>)}</select>
          <span className="mt-1 block text-xs text-slate-500">Solo aparecen cursos publicados y vigentes.</span></label>
        <div><span className="etiqueta">Personas</span><Personas r={r} valor={d.usuario_ids} onCambio={(v: number[]) => setD({ ...d, usuario_ids: v })} /></div>
        {r.equipos.length > 0 && <div><span className="etiqueta">Equipos</span>
          <div className="flex flex-wrap gap-3">{r.equipos.map((e: any) => (
            <label key={e.id} className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.equipo_ids.includes(e.id)}
              onChange={(x) => setD({ ...d, equipo_ids: x.target.checked ? [...d.equipo_ids, e.id] : d.equipo_ids.filter((y: number) => y !== e.id) })} />{e.nombre}</label>))}</div></div>}
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Tipo</span><select className="campo" value={d.tipo} onChange={(e) => setD({ ...d, tipo: e.target.value })}>
            <option value="obligatorio">Obligatorio</option><option value="recomendado">Recomendado</option></select></label>
          <label><span className="etiqueta">Fecha sugerida para terminar</span><input className="campo" type="date" value={d.fecha_sugerida} onChange={(e) => setD({ ...d, fecha_sugerida: e.target.value })} /></label>
        </div>
        <div className="flex justify-end"><button className="btn-turquesa" disabled={!d.curso_id || (!d.usuario_ids.length && !d.equipo_ids.length)}>Asignar curso</button></div>
      </form>
    </Modal>
  );
}

function EditarEquipo({ r, e, onCerrar, hacer }: any) {
  const [d, setD] = useState<any>({ nombre: e?.nombre || "", descripcion: e?.descripcion || "", usuario_ids: e?.miembros.map((x: any) => x.id) || [] });
  return (
    <Modal titulo={e ? "Editar equipo" : "Nuevo equipo"} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (x) => {
        x.preventDefault();
        if (await hacer(() => e ? api.put(`/academia/equipos/${e.id}`, d) : api.post("/academia/equipos", d), "Equipo guardado.")) onCerrar();
      }}>
        <input className="campo" required minLength={2} placeholder="Nombre (p. ej. Litigio)" value={d.nombre} onChange={(x) => setD({ ...d, nombre: x.target.value })} />
        <input className="campo" placeholder="Descripción (opcional)" value={d.descripcion} onChange={(x) => setD({ ...d, descripcion: x.target.value })} />
        <Personas r={r} valor={d.usuario_ids} onCambio={(v: number[]) => setD({ ...d, usuario_ids: v })} />
        <div className="flex justify-end"><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function Instructores({ r, hacer }: any) {
  const [ids, setIds] = useState<number[]>(r.instructores);
  return (
    <section className="tarjeta p-4 text-sm">
      <h2 className="font-semibold text-marino">Instructores</h2>
      <p className="mb-2 text-xs text-slate-500">Pueden crear y editar cursos del despacho y ver el avance de los cursos que crean. Los administradores ya tienen estos permisos.</p>
      <div className="flex flex-wrap gap-3">
        {r.usuarios.filter((u: any) => u.activo && u.rol === "analista").map((u: any) => (
          <label key={u.id} className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={ids.includes(u.id)}
            onChange={(e) => setIds(e.target.checked ? [...ids, u.id] : ids.filter((x) => x !== u.id))} />{u.nombre}</label>))}
        {r.usuarios.filter((u: any) => u.activo && u.rol === "analista").length === 0 && <span className="text-xs text-slate-400">No hay usuarios con rol «analista».</span>}
      </div>
      <button className="btn-sec mt-3" onClick={() => hacer(() => api.put("/academia/instructores", { usuario_ids: ids }), "Instructores actualizados.")}>Guardar instructores</button>
    </section>
  );
}
