"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AcademiaShell, Insignia } from "@/components/academia";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha, fechaHora } from "@/lib/api";

/** Editor de un curso del despacho. Cada cambio de contenido sube la versión y la fecha de
 *  actualización; nada borra el avance de quien ya lo tomó. */
export default function EditorCurso() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [editando, setEditando] = useState<any>(null);
  const [publicar, setPublicar] = useState(false);
  const cargar = useCallback(() => api.get(`/academia/admin/cursos/${id}`).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(fn: () => Promise<any>, exito: string) {
    setError(""); setOk("");
    try { const r = await fn(); if (r?.modulos) setC(r); else await cargar(); setOk(exito); return true; } catch (e: any) { setError(e.message); return false; }
  }
  if (!c) return <AcademiaShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AcademiaShell>;
  if (!c.editable) return <AcademiaShell><Aviso tipo="info">Este curso no se puede editar desde su cuenta. Si es un curso de Nomira, duplíquelo para adaptarlo.</Aviso></AcademiaShell>;
  return (
    <AcademiaShell>
      <Link href="/academia/administrar" className="text-sm font-semibold text-turquesa-700 hover:underline">← Administrar cursos</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">{c.titulo}</h1>
          <p className="text-sm text-slate-500"><Insignia clase={c.estado === "publicado" ? "bg-emerald-100 text-emerald-800" : c.estado === "borrador" ? "bg-amber-100 text-amber-800" : "bg-slate-200 text-slate-600"}>{c.estado_texto}</Insignia>
            {" "}Versión {c.version} · Actualizado {fechaHora(c.actualizado_en)}{c.publicado_por ? ` · Publicó ${c.publicado_por}` : ""}{c.revisado_por ? ` · Revisó ${c.revisado_por}` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn-sec" href={`/academia/cursos/${c.id}`}>Vista previa</Link>
          {c.estado !== "publicado" && <button className="btn-turquesa" onClick={() => setPublicar(true)}>Publicar</button>}
          {c.estado === "publicado" && <button className="btn-sec" onClick={() => hacer(() => api.post(`/academia/admin/cursos/${id}/despublicar`), "El curso volvió a borrador.")}>Pasar a borrador</button>}
          {c.estado !== "archivado" ? <button className="btn-peligro" onClick={() => hacer(() => api.post(`/academia/admin/cursos/${id}/archivar`), "Curso archivado. El historial y las constancias se conservan.")}>Archivar</button>
            : <button className="btn-sec" onClick={() => hacer(() => api.post(`/academia/admin/cursos/${id}/restaurar`), "Curso restaurado como borrador.")}>Restaurar</button>}
        </div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {c.estado === "publicado" && <div className="mb-4"><Aviso tipo="info">El curso está publicado: los cambios se ven de inmediato. Quien ya lo completó conserva su constancia.</Aviso></div>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Contenido c={c} hacer={hacer} setEditando={setEditando} />
          <Preguntas c={c} hacer={hacer} />
        </div>
        <div className="space-y-5">
          <Ficha c={c} hacer={hacer} />
          <Vigencia c={c} hacer={hacer} />
          <Sesiones c={c} hacer={hacer} />
        </div>
      </div>
      {editando && <EditarLeccion c={c} l={editando} hacer={hacer} onCerrar={() => setEditando(null)} />}
      {publicar && (
        <Modal titulo="Publicar curso" onCerrar={() => setPublicar(false)}>
          <PublicarForm c={c} onPublicar={async (revisado: boolean) => { if (await hacer(() => api.post(`/academia/admin/cursos/${id}/publicar`, { revisado }), "Curso publicado.")) setPublicar(false); }} />
        </Modal>)}
    </AcademiaShell>
  );
}

function PublicarForm({ c, onPublicar }: any) {
  const [revisado, setRevisado] = useState(false);
  const exige = c.juridico || c.asistido_ia;
  return (
    <div className="space-y-3 text-sm">
      <p>Al publicarlo, su equipo podrá verlo en «Cursos» y usted podrá asignarlo.</p>
      {exige && <p className="rounded-xl bg-amber-50 p-3 text-amber-900">Este curso {c.juridico ? "tiene contenido jurídico" : ""}{c.juridico && c.asistido_ia ? " y " : ""}{c.asistido_ia ? "se preparó con ayuda de IA" : ""}: una persona autorizada debe revisarlo. Nomira no lo valida automáticamente.</p>}
      <label className="flex items-start gap-2"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={revisado} onChange={(e) => setRevisado(e.target.checked)} />
        <span>Revisé el contenido y confirmo que está correcto y vigente{exige ? " (obligatorio)" : ""}. Quedará registrado con mi nombre.</span></label>
      <div className="flex justify-end"><button className="btn-turquesa" disabled={exige && !revisado} onClick={() => onPublicar(revisado)}>Publicar</button></div>
    </div>
  );
}

function Contenido({ c, hacer, setEditando }: any) {
  const [mod, setMod] = useState("");
  const [nuevaLeccion, setNuevaLeccion] = useState<Record<number, string>>({});
  return (
    <section className="tarjeta p-5">
      <h2 className="mb-3 font-semibold text-marino">Módulos y lecciones</h2>
      <div className="space-y-4">
        {c.modulos.map((m: any, i: number) => (
          <div key={m.id} className="rounded-xl border border-crema-300">
            <div className="flex flex-wrap items-center gap-2 border-b border-crema-300 bg-crema/50 px-3 py-2">
              <input className="campo min-w-0 flex-1 py-1 font-semibold" defaultValue={m.titulo} aria-label="Título del módulo"
                onBlur={(e) => e.target.value.trim() && e.target.value !== m.titulo && hacer(() => api.patch(`/academia/admin/modulos/${m.id}`, { titulo: e.target.value }), "Módulo actualizado.")} />
              <button className="btn-sec px-2 py-1 text-xs" disabled={i === 0} onClick={() => hacer(() => api.patch(`/academia/admin/modulos/${m.id}`, { mover: "arriba" }), "Orden actualizado.")} aria-label="Subir módulo">↑</button>
              <button className="btn-sec px-2 py-1 text-xs" disabled={i === c.modulos.length - 1} onClick={() => hacer(() => api.patch(`/academia/admin/modulos/${m.id}`, { mover: "abajo" }), "Orden actualizado.")} aria-label="Bajar módulo">↓</button>
              <button className="btn-peligro px-2 py-1 text-xs" onClick={() => hacer(() => api.borrar(`/academia/admin/modulos/${m.id}`), "Módulo archivado.")}>Quitar</button>
            </div>
            <ol className="divide-y divide-crema-200">
              {m.lecciones.map((l: any, j: number) => (
                <li key={l.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="min-w-0 flex-1"><b className="text-marino">{l.titulo}</b>
                    <span className="block text-xs text-slate-500">{[l.video_url && "video", l.sesion_url && "sesión", l.texto && "lectura", l.archivo && "material", l.actividad && "pregunta", l.recursos.length && `${l.recursos.length} enlace(s)`].filter(Boolean).join(" · ") || "Sin contenido todavía"}</span></span>
                  <button className="btn-sec px-2 py-1 text-xs" disabled={j === 0} onClick={() => hacer(() => api.patch(`/academia/admin/lecciones/${l.id}`, { mover: "arriba" }), "Orden actualizado.")} aria-label="Subir lección">↑</button>
                  <button className="btn-sec px-2 py-1 text-xs" disabled={j === m.lecciones.length - 1} onClick={() => hacer(() => api.patch(`/academia/admin/lecciones/${l.id}`, { mover: "abajo" }), "Orden actualizado.")} aria-label="Bajar lección">↓</button>
                  <button className="btn-sec px-2 py-1 text-xs" onClick={() => setEditando(l)}>Editar</button>
                  <button className="btn-peligro px-2 py-1 text-xs" onClick={() => hacer(() => api.borrar(`/academia/admin/lecciones/${l.id}`), "Lección archivada. El avance de quien ya la tomó se conserva.")}>Quitar</button>
                </li>))}
            </ol>
            <form className="flex gap-2 p-3" onSubmit={(e) => { e.preventDefault(); const t = nuevaLeccion[m.id]; if (t?.trim()) hacer(() => api.post(`/academia/admin/modulos/${m.id}/lecciones`, { titulo: t }), "Lección agregada: edítela para agregar contenido.").then(() => setNuevaLeccion({ ...nuevaLeccion, [m.id]: "" })); }}>
              <input className="campo" placeholder="Título de una nueva lección" value={nuevaLeccion[m.id] || ""} onChange={(e) => setNuevaLeccion({ ...nuevaLeccion, [m.id]: e.target.value })} />
              <button className="btn-sec whitespace-nowrap">+ Lección</button>
            </form>
          </div>))}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (mod.trim()) hacer(() => api.post(`/academia/admin/cursos/${c.id}/modulos`, { titulo: mod }), "Módulo agregado.").then(() => setMod("")); }}>
        <input className="campo" placeholder="Nombre de un nuevo módulo" value={mod} onChange={(e) => setMod(e.target.value)} />
        <button className="btn-sec whitespace-nowrap">+ Módulo</button>
      </form>
    </section>
  );
}

function EditarLeccion({ c, l, hacer, onCerrar }: any) {
  const [d, setD] = useState<any>({ titulo: l.titulo, texto: l.texto || "", video_url: l.video_url || "", sesion_url: l.sesion_url || "", transcripcion: l.transcripcion || "",
    duracion_min: l.duracion_min || "", recursos: (l.recursos || []).map((r: any) => `${r.titulo} | ${r.url}`).join("\n"),
    act: !!l.actividad, pregunta: l.actividad?.pregunta || "", opciones: (l.actividad?.opciones || ["", ""]).join("\n"), correcta: l.actividad?.correcta ?? 0, explicacion: l.actividad?.explicacion || "" });
  const [archivo, setArchivo] = useState<File | null>(null);
  const actual = c.modulos.flatMap((m: any) => m.lecciones).find((x: any) => x.id === l.id) || l;
  const opciones = d.opciones.split("\n").map((x: string) => x.trim()).filter(Boolean);
  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    const recursos = d.recursos.split("\n").map((x: string) => x.split("|").map((y: string) => y.trim())).filter((x: string[]) => x[0] && x[1]).map(([titulo, url]: string[]) => ({ titulo, url }));
    const cuerpo: any = { titulo: d.titulo, texto: d.texto || null, video_url: d.video_url || null, sesion_url: d.sesion_url || null, transcripcion: d.transcripcion || null,
      duracion_min: d.duracion_min ? Number(d.duracion_min) : null, recursos };
    if (d.act) cuerpo.actividad = { pregunta: d.pregunta, opciones, correcta: Number(d.correcta), explicacion: d.explicacion || null };
    else cuerpo.quitar_actividad = true;
    if (await hacer(() => api.patch(`/academia/admin/lecciones/${l.id}`, cuerpo), "Lección guardada.")) onCerrar();
  }
  return (
    <Modal titulo="Editar lección" onCerrar={onCerrar} ancho="max-w-3xl">
      <form className="space-y-3" onSubmit={guardar}>
        <label className="block"><span className="etiqueta">Título</span><input className="campo" required minLength={2} value={d.titulo} onChange={(e) => setD({ ...d, titulo: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Texto breve</span><textarea className="campo" rows={6} value={d.texto} onChange={(e) => setD({ ...d, texto: e.target.value })} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Video (enlace https: YouTube, Vimeo u otro)</span><input className="campo" value={d.video_url} onChange={(e) => setD({ ...d, video_url: e.target.value })} /></label>
          <label><span className="etiqueta">Enlace a sesión (Zoom, Meet, Teams…)</span><input className="campo" value={d.sesion_url} onChange={(e) => setD({ ...d, sesion_url: e.target.value })} /></label>
          <label><span className="etiqueta">Duración (min)</span><input className="campo" type="number" min={1} value={d.duracion_min} onChange={(e) => setD({ ...d, duracion_min: e.target.value })} /></label>
        </div>
        <p className="text-xs text-slate-500">Nomira no aloja videos: YouTube y Vimeo se muestran dentro de la lección; otros se abren en su sitio.</p>
        <label className="block"><span className="etiqueta">Subtítulos o transcripción (accesibilidad)</span><textarea className="campo" rows={3} value={d.transcripcion} onChange={(e) => setD({ ...d, transcripcion: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Recursos y enlaces (uno por línea: Título | https://…)</span><textarea className="campo font-mono text-xs" rows={3} value={d.recursos} onChange={(e) => setD({ ...d, recursos: e.target.value })} /></label>
        <div className="rounded-xl border border-crema-300 p-3">
          <span className="etiqueta">Material descargable (PDF, Word, Excel, PowerPoint, imagen; hasta 25 MB)</span>
          {actual.archivo ? <p className="text-sm">{actual.archivo.nombre} <button type="button" className="ml-2 text-xs font-semibold text-red-700 hover:underline" onClick={() => hacer(() => api.borrar(`/academia/admin/lecciones/${l.id}/archivo`), "Material quitado.")}>Quitar</button></p>
            : <div className="flex flex-wrap gap-2"><input type="file" className="text-sm" accept=".pdf,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.txt" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
              <button type="button" className="btn-sec" disabled={!archivo} onClick={() => { const f = new FormData(); f.append("archivo", archivo!); hacer(() => api.subir(`/academia/admin/lecciones/${l.id}/archivo`, f), "Material cargado."); }}>Subir</button></div>}
        </div>
        <div className="rounded-xl border border-turquesa/40 p-3">
          <label className="flex items-center gap-2 text-sm font-semibold text-marino"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.act} onChange={(e) => setD({ ...d, act: e.target.checked })} />Pregunta de comprobación</label>
          {d.act && <div className="mt-2 space-y-2">
            <input className="campo" required placeholder="Pregunta" value={d.pregunta} onChange={(e) => setD({ ...d, pregunta: e.target.value })} />
            <textarea className="campo" rows={3} placeholder="Opciones (una por línea)" value={d.opciones} onChange={(e) => setD({ ...d, opciones: e.target.value })} />
            <label className="block"><span className="etiqueta">Respuesta correcta</span><select className="campo" value={d.correcta} onChange={(e) => setD({ ...d, correcta: e.target.value })}>
              {opciones.map((o: string, i: number) => <option key={i} value={i}>{o}</option>)}</select></label>
            <input className="campo" placeholder="Explicación (se muestra al responder)" value={d.explicacion} onChange={(e) => setD({ ...d, explicacion: e.target.value })} />
          </div>}
        </div>
        <div className="flex justify-end"><button className="btn-turquesa">Guardar lección</button></div>
      </form>
    </Modal>
  );
}

function Preguntas({ c, hacer }: any) {
  const vacia = { texto: "", opciones: "", correcta: 0, explicacion: "" };
  const [d, setD] = useState<any>(vacia);
  const ops = d.opciones.split("\n").map((x: string) => x.trim()).filter(Boolean);
  return (
    <section className="tarjeta p-5">
      <h2 className="font-semibold text-marino">Cuestionario final</h2>
      <p className="mb-3 text-xs text-slate-500">{c.calificacion_minima ? `Se requiere ${c.calificacion_minima}/100 para completar el curso.` : "Sin calificación mínima: el curso se completa al terminar las lecciones (el cuestionario es opcional)."}</p>
      <ol className="space-y-2 text-sm">
        {c.preguntas.map((p: any, i: number) => (
          <li key={p.id} className="rounded-xl border border-crema-300 p-3">
            <div className="flex items-start justify-between gap-2"><b>{i + 1}. {p.texto}</b>
              <button className="text-xs font-semibold text-red-700 hover:underline" onClick={() => hacer(() => api.borrar(`/academia/admin/preguntas/${p.id}`), "Pregunta quitada.")}>Quitar</button></div>
            <ul className="mt-1 text-xs text-slate-600">{p.opciones.map((o: string, j: number) => <li key={j} className={j === p.correcta ? "font-semibold text-emerald-700" : ""}>{j === p.correcta ? "✓ " : "· "}{o}</li>)}</ul>
          </li>))}
      </ol>
      <form className="mt-3 space-y-2 border-t border-crema-300 pt-3" onSubmit={(e) => { e.preventDefault();
        hacer(() => api.post(`/academia/admin/cursos/${c.id}/preguntas`, { texto: d.texto, opciones: ops, correcta: Number(d.correcta), explicacion: d.explicacion || null }), "Pregunta agregada.").then((x: any) => x && setD(vacia)); }}>
        <input className="campo" required minLength={3} placeholder="Nueva pregunta" value={d.texto} onChange={(e) => setD({ ...d, texto: e.target.value })} />
        <textarea className="campo" rows={3} required placeholder="Opciones (una por línea)" value={d.opciones} onChange={(e) => setD({ ...d, opciones: e.target.value })} />
        <div className="flex flex-wrap gap-2">
          <select className="campo w-auto" value={d.correcta} onChange={(e) => setD({ ...d, correcta: e.target.value })} aria-label="Respuesta correcta">
            {ops.length === 0 && <option value={0}>Respuesta correcta</option>}{ops.map((o: string, i: number) => <option key={i} value={i}>Correcta: {o}</option>)}</select>
          <input className="campo min-w-0 flex-1" placeholder="Explicación (opcional)" value={d.explicacion} onChange={(e) => setD({ ...d, explicacion: e.target.value })} />
          <button className="btn-sec">+ Pregunta</button>
        </div>
      </form>
    </section>
  );
}

function Ficha({ c, hacer }: any) {
  const [d, setD] = useState<any>({ titulo: c.titulo, materia: c.materia, roles: (c.roles || []).join(", "), instructor: c.instructor || "", institucion: c.institucion || "",
    descripcion: c.descripcion || "", duracion_min: c.duracion_min || "", modalidad: c.modalidad, juridico: c.juridico, asistido_ia: c.asistido_ia,
    calificacion_minima: c.calificacion_minima || "" });
  return (
    <section className="tarjeta p-5">
      <h2 className="mb-3 font-semibold text-marino">Ficha del curso</h2>
      <form className="grid gap-2" onSubmit={(e) => { e.preventDefault();
        hacer(() => api.patch(`/academia/admin/cursos/${c.id}`, { ...d, roles: d.roles.split(",").map((x: string) => x.trim()).filter(Boolean),
          duracion_min: d.duracion_min ? Number(d.duracion_min) : null, calificacion_minima: d.calificacion_minima ? Number(d.calificacion_minima) : null }), "Ficha guardada."); }}>
        {[["titulo", "Título"], ["materia", "Materia"], ["roles", "Dirigido a (separado por comas)"], ["instructor", "Instructor o autor"], ["institucion", "Institución (si aplica)"]].map(([k, t]) => (
          <label key={k}><span className="etiqueta">{t}</span><input className="campo" value={d[k]} onChange={(e) => setD({ ...d, [k]: e.target.value })} /></label>))}
        <label><span className="etiqueta">Descripción breve</span><textarea className="campo" rows={3} value={d.descripcion} onChange={(e) => setD({ ...d, descripcion: e.target.value })} /></label>
        <div className="grid grid-cols-2 gap-2">
          <label><span className="etiqueta">Duración (min)</span><input className="campo" type="number" min={1} value={d.duracion_min} onChange={(e) => setD({ ...d, duracion_min: e.target.value })} /></label>
          <label><span className="etiqueta">Modalidad</span><select className="campo" value={d.modalidad} onChange={(e) => setD({ ...d, modalidad: e.target.value })}>
            <option value="autodirigido">Autodirigido</option><option value="en_vivo">En vivo</option><option value="combinado">Combinado</option></select></label>
        </div>
        <label><span className="etiqueta">Calificación mínima del cuestionario (vacío = solo completar lecciones)</span>
          <input className="campo" type="number" min={1} max={100} value={d.calificacion_minima} onChange={(e) => setD({ ...d, calificacion_minima: e.target.value })} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.juridico} onChange={(e) => setD({ ...d, juridico: e.target.checked })} />Contenido jurídico</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.asistido_ia} onChange={(e) => setD({ ...d, asistido_ia: e.target.checked })} />Preparado con ayuda de IA</label>
        <button className="btn-turquesa justify-self-start">Guardar ficha</button>
      </form>
      <p className="mt-2 text-xs text-slate-500">Creado el {fecha(c.creado_en)}{c.creado_por ? ` por ${c.creado_por}` : ""}.</p>
    </section>
  );
}

function Vigencia({ c, hacer }: any) {
  const [nota, setNota] = useState(c.nota_revision || "");
  return (
    <section className="tarjeta p-5 text-sm">
      <h2 className="font-semibold text-marino">Vigencia del contenido</h2>
      {c.aviso_vigencia ? <div className="mt-2"><Aviso tipo="alerta">{c.aviso_vigencia}</Aviso></div> : <p className="mt-1 text-slate-600">Sin avisos. Última actualización: {fecha(c.actualizado_en)}.</p>}
      <p className="mt-2 text-xs text-slate-500">Si el material puede haber quedado desactualizado, márquelo: su equipo verá el aviso y el curso dejará de recomendarse y asignarse hasta que lo revise.</p>
      <textarea className="campo mt-2" rows={2} maxLength={500} placeholder="Nota para el equipo (p. ej. «Cambió el procedimiento en 2026»)" value={nota} onChange={(e) => setNota(e.target.value)} />
      <div className="mt-2 flex flex-wrap gap-2">
        <button className="btn-sec" onClick={() => hacer(() => api.patch(`/academia/admin/cursos/${c.id}`, { requiere_revision: true, nota_revision: nota || null }), "Curso marcado para revisión.")}>Marcar para revisión</button>
        {c.requiere_revision && <button className="btn-turquesa" onClick={() => hacer(() => api.patch(`/academia/admin/cursos/${c.id}`, { requiere_revision: false }), "Revisión registrada con su nombre.")}>Ya lo revisé: está vigente</button>}
      </div>
    </section>
  );
}

function Sesiones({ c, hacer }: any) {
  const [d, setD] = useState<any>({ titulo: "", inicio: "", duracion_min: 60, enlace: "" });
  return (
    <section className="tarjeta p-5 text-sm">
      <h2 className="font-semibold text-marino">Sesiones en vivo</h2>
      <p className="text-xs text-slate-500">Nomira no crea reuniones: pegue el enlace de Zoom, Google Meet o Teams.</p>
      <ul className="mt-2 space-y-2">
        {c.sesiones.map((s: any) => (
          <li key={s.id} className={`rounded-xl border border-crema-300 p-2 ${s.cancelada ? "opacity-60" : ""}`}><b>{s.titulo}</b> · {fechaHora(s.inicio)} · {s.duracion_min} min{s.cancelada ? " · cancelada" : ""}
            {!s.cancelada && <button className="ml-2 text-xs font-semibold text-red-700 hover:underline" onClick={() => hacer(() => api.patch(`/academia/admin/sesiones/${s.id}`, { ...s, cancelada: true }), "Sesión cancelada.")}>Cancelar</button>}</li>))}
      </ul>
      <form className="mt-3 grid gap-2" onSubmit={(e) => { e.preventDefault();
        hacer(() => api.post(`/academia/admin/cursos/${c.id}/sesiones`, { ...d, inicio: new Date(d.inicio).toISOString(), enlace: d.enlace || null, duracion_min: Number(d.duracion_min) }), "Sesión agregada.")
          .then((x: any) => x && setD({ titulo: "", inicio: "", duracion_min: 60, enlace: "" })); }}>
        <input className="campo" required minLength={3} placeholder="Título de la sesión" value={d.titulo} onChange={(e) => setD({ ...d, titulo: e.target.value })} />
        <div className="grid grid-cols-2 gap-2"><input className="campo" type="datetime-local" required value={d.inicio} onChange={(e) => setD({ ...d, inicio: e.target.value })} aria-label="Inicio" />
          <input className="campo" type="number" min={10} value={d.duracion_min} onChange={(e) => setD({ ...d, duracion_min: e.target.value })} aria-label="Duración (min)" /></div>
        <input className="campo" placeholder="Enlace https:// (opcional)" value={d.enlace} onChange={(e) => setD({ ...d, enlace: e.target.value })} />
        <button className="btn-sec justify-self-start">+ Sesión</button>
      </form>
    </section>
  );
}
