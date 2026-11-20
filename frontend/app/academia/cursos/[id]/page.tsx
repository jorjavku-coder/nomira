"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AcademiaShell, Barra, Insignia } from "@/components/academia";
import { Aviso } from "@/components/ui";
import { api, fecha, fechaHora } from "@/lib/api";

const ICONO: Record<string, string> = { video: "Video", sesion: "Sesión", documento: "Material", texto: "Lectura", actividad: "Pregunta", recursos: "Enlaces" };

export default function Curso() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [iniciando, setIniciando] = useState(false);
  useEffect(() => { api.get(`/academia/cursos/${id}`).then(setC).catch((e) => setError(e.message)); }, [id]);
  async function empezar() {
    setIniciando(true); setError("");
    try {
      const r = await api.post(`/academia/cursos/${id}/iniciar`);
      router.push(r.leccion_id ? `/academia/lecciones/${r.leccion_id}` : `/academia/cursos/${id}/cuestionario`);
    } catch (e: any) { setError(e.message); setIniciando(false); }
  }
  if (!c) return <AcademiaShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AcademiaShell>;
  const pr = c.progreso;
  return (
    <AcademiaShell>
      <Link href="/academia/cursos" className="text-sm font-semibold text-turquesa-700 hover:underline">← Cursos</Link>
      <div className="mt-2 grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {c.asignacion && <Insignia clase={c.asignacion.tipo === "obligatorio" ? "bg-marino text-white" : "bg-turquesa-50 text-turquesa-700"}>{c.asignacion.tipo_texto}</Insignia>}
            {c.origen === "nomira" && <Insignia>Curso de Nomira</Insignia>}
            {c.estado !== "publicado" && <Insignia clase="bg-amber-100 text-amber-800">{c.estado === "borrador" ? "Borrador (vista previa)" : "Archivado"}</Insignia>}
          </div>
          <h1 className="text-3xl font-extrabold text-marino">{c.titulo}</h1>
          {c.descripcion && <p className="mt-2 text-slate-700">{c.descripcion}</p>}
          {c.aviso_vigencia && <div className="mt-3"><Aviso tipo="alerta">{c.aviso_vigencia}</Aviso></div>}
          {c.completado_version_anterior && <div className="mt-3"><Aviso tipo="info">Usted completó una versión anterior de este curso. Su constancia sigue vigente; el contenido nuevo es opcional.</Aviso></div>}
          <Aviso>{error}</Aviso>
          <div className="mt-6 space-y-4">
            {c.modulos.map((m: any, i: number) => (
              <section key={m.id} className="tarjeta overflow-hidden">
                <h2 className="border-b border-crema-300 bg-crema/50 px-4 py-2.5 font-semibold text-marino">{i + 1}. {m.titulo}</h2>
                <ol className="divide-y divide-crema-200">
                  {m.lecciones.length === 0 && <li className="px-4 py-3 text-sm text-slate-400">Sin lecciones.</li>}
                  {m.lecciones.map((l: any) => (
                    <li key={l.id}><Link href={`/academia/lecciones/${l.id}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm hover:bg-crema/40">
                      <span className="flex items-center gap-2">
                        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] ${l.completada ? "bg-emerald-500 text-white" : "border border-crema-300 text-transparent"}`} aria-label={l.completada ? "Completada" : "Pendiente"}>✓</span>
                        <span className="text-marino">{l.titulo}</span></span>
                      <span className="text-xs text-slate-500">{l.tiene.map((t: string) => ICONO[t]).join(" · ")}{l.duracion_min ? ` · ${l.duracion_min} min` : ""}</span>
                    </Link></li>))}
                </ol>
              </section>))}
            {c.cuestionario.preguntas > 0 && (
              <section className="tarjeta p-4 text-sm">
                <h2 className="font-semibold text-marino">Cuestionario final</h2>
                <p className="text-slate-600">{c.cuestionario.preguntas} preguntas · {c.cuestionario.calificacion_minima ? `Calificación mínima: ${c.cuestionario.calificacion_minima}` : "Sin calificación mínima"}
                  {c.cuestionario.calificacion !== null && ` · Su mejor resultado: ${c.cuestionario.calificacion}`}</p>
                {c.cuestionario.disponible ? <Link className="btn-sec mt-2" href={`/academia/cursos/${c.id}/cuestionario`}>{c.cuestionario.aprobado ? "Repetir cuestionario" : "Responder cuestionario"}</Link>
                  : <p className="mt-1 text-xs text-slate-500">Se habilita al completar todas las lecciones.</p>}
              </section>)}
          </div>
        </div>
        <aside className="space-y-4">
          <section className="tarjeta p-5">
            {pr.estado !== "sin_iniciar" && <><Barra valor={pr.porcentaje} /><p className="mt-1 text-sm text-slate-600">{pr.texto}</p></>}
            {c.estado === "publicado" && pr.estado !== "completado" && (
              <button className="btn-turquesa mt-3 w-full py-2.5 text-base" disabled={iniciando} onClick={empezar}>{pr.estado === "en_curso" ? "Continuar curso" : "Iniciar curso"}</button>)}
            {c.constancia && (
              <div className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">
                <b>¡Curso completado!</b> el {fecha(c.completado_en)}.
                <button className="btn-sec mt-2 w-full" onClick={() => api.descargar(`/academia/constancias/${c.avance_id}`, "constancia.pdf").catch((e) => setError(e.message))}>Descargar constancia de participación</button>
                <p className="mt-1 text-xs">Folio {c.constancia_folio}. Es una constancia de participación interna, no una certificación oficial.</p>
              </div>)}
            {c.asignacion?.fecha_sugerida && pr.estado !== "completado" && <p className="mt-2 text-xs text-slate-500">Fecha sugerida para terminar: {fecha(c.asignacion.fecha_sugerida)}</p>}
            {c.puede_editar && <Link className="btn-sec mt-3 w-full" href={`/academia/administrar/${c.id}`}>Editar curso</Link>}
          </section>
          <section className="tarjeta p-5 text-sm">
            <h2 className="mb-2 font-semibold text-marino">Sobre el contenido</h2>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <dt className="text-slate-500">Materia</dt><dd>{c.materia}</dd>
              <dt className="text-slate-500">Autor o instructor</dt><dd>{c.instructor || "—"}</dd>
              <dt className="text-slate-500">Institución</dt><dd>{c.institucion || "No aplica"}</dd>
              <dt className="text-slate-500">Duración</dt><dd>{c.duracion_min ? `${c.duracion_min} min` : "—"}</dd>
              <dt className="text-slate-500">Modalidad</dt><dd>{c.modalidad_texto}</dd>
              <dt className="text-slate-500">Creado</dt><dd>{fecha(c.creado_en)}</dd>
              <dt className="text-slate-500">Actualizado</dt><dd>{fecha(c.actualizado_en)}</dd>
              {c.revisado_por && <><dt className="text-slate-500">Revisado por</dt><dd>{c.revisado_por} ({fecha(c.revisado_en)})</dd></>}
              {c.roles.length > 0 && <><dt className="text-slate-500">Dirigido a</dt><dd>{c.roles.join(", ")}</dd></>}
            </dl>
            {c.juridico && <p className="mt-3 text-xs text-slate-500">Contenido jurídico preparado y revisado por personas del despacho. Verifique su vigencia antes de aplicarlo a un caso.</p>}
            {c.asistido_ia && <p className="mt-1 text-xs text-slate-500">Este material se preparó con ayuda de IA y fue revisado por una persona autorizada antes de publicarse.</p>}
          </section>
          {c.sesiones.length > 0 && (
            <section className="tarjeta p-5 text-sm">
              <h2 className="mb-2 font-semibold text-marino">Sesiones en vivo</h2>
              <ul className="space-y-2">{c.sesiones.map((s: any) => (
                <li key={s.id}><b>{s.titulo}</b><span className="block text-xs text-slate-500">{fechaHora(s.inicio)} · {s.duracion_min} min</span>
                  {s.enlace && <a className="text-xs font-semibold text-turquesa-700 underline" href={s.enlace} target="_blank" rel="noopener noreferrer">Enlace de la sesión</a>}
                  {s.grabacion_url && <a className="ml-2 text-xs font-semibold text-turquesa-700 underline" href={s.grabacion_url} target="_blank" rel="noopener noreferrer">Grabación</a>}</li>))}</ul>
            </section>)}
        </aside>
      </div>
    </AcademiaShell>
  );
}
