"use client";
import Link from "next/link";
import BotonAyuda from "@/components/BotonAyuda";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Shell from "@/components/Shell";
import { api, fecha, fechaHora, mxn } from "@/lib/api";

let permisos: any = null;
export function usePermisosAcademia(): { es_instructor: boolean; es_admin: boolean } | null {
  const [p, setP] = useState<any>(permisos);
  useEffect(() => { if (!permisos) api.get("/academia/yo").then((x) => { permisos = x; setP(x); }).catch(() => {}); }, []);
  return p;
}

/** Marco de Nomira Academia: «Mi aprendizaje», «Cursos», «Equipo» y «Administrar». */
export function AcademiaShell({ children }: { children: React.ReactNode }) {
  const ruta = usePathname();
  const p = usePermisosAcademia();
  const enlaces: [string, string, boolean][] = [
    ["/academia", "Mi aprendizaje", ruta === "/academia"],
    ["/academia/cursos", "Cursos", ruta.startsWith("/academia/cursos") || ruta.startsWith("/academia/lecciones")],
    ...(p?.es_instructor ? [["/academia/equipo", "Equipo", ruta.startsWith("/academia/equipo")], ["/academia/administrar", "Administrar", ruta.startsWith("/academia/administrar")]] as [string, string, boolean][] : []),
  ];
  return (
    <Shell>
      <div className="mb-1 flex items-center justify-between gap-2"><div><p className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">Nomira Academia</p>
        <p className="text-sm text-slate-500">Capacitación de su equipo: cursos cortos, cuestionarios y constancias; usted ve quién ya terminó.</p></div><BotonAyuda modulo="academia" /></div>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-crema-300" aria-label="Nomira Academia">
        {enlaces.map(([href, t, activo]) => (
          <Link key={href} href={href} aria-current={activo ? "page" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${activo ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>{t}</Link>
        ))}
      </nav>
      {children}
    </Shell>
  );
}

export function Barra({ valor, etiqueta }: { valor: number; etiqueta?: string }) {
  return (
    <div>
      <div className="h-2 overflow-hidden rounded-full bg-crema-300" role="progressbar" aria-valuenow={valor} aria-valuemin={0} aria-valuemax={100} aria-label={etiqueta || "Avance"}>
        <div className={`h-full rounded-full ${valor >= 100 ? "bg-emerald-500" : "bg-turquesa"}`} style={{ width: `${Math.max(valor, valor > 0 ? 4 : 0)}%` }} />
      </div>
    </div>
  );
}

export function Insignia({ clase = "bg-slate-100 text-slate-700", children }: { clase?: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${clase}`}>{children}</span>;
}

export function Ficha({ c }: { c: any }) {
  return (
    <p className="text-xs text-slate-500">
      {[c.materia, c.institucion ? `${c.instructor ? `${c.instructor} · ` : ""}${c.institucion}` : c.instructor, c.duracion_min ? `${c.duracion_min} min` : null,
        c.modalidad_texto, `Actualizado ${fecha(c.actualizado_en)}`].filter(Boolean).join(" · ")}
    </p>
  );
}

/** Tarjeta de curso: título, materia, instructor, duración, modalidad, actualización, descripción y avance. */
export function TarjetaCurso({ c, compacta = false }: { c: any; compacta?: boolean }) {
  const pr = c.progreso;
  const bloqueado = c.acceso?.tipo === "pago" && !c.acceso.tiene_acceso;
  const boton = bloqueado ? "Ver curso y precio" : pr.estado === "completado" ? "Ver curso" : pr.estado === "en_curso" ? "Continuar curso" : "Iniciar curso";
  const destino = pr.estado === "en_curso" && (c.ultima_leccion_id || pr.siguiente_leccion_id) ? `/academia/lecciones/${c.ultima_leccion_id || pr.siguiente_leccion_id}` : `/academia/cursos/${c.id}`;
  return (
    <article className="tarjeta flex flex-col p-4">
      <div className="mb-1 flex flex-wrap gap-1.5">
        {c.asignacion && <Insignia clase={c.asignacion.tipo === "obligatorio" ? "bg-marino text-white" : "bg-turquesa-50 text-turquesa-700"}>{c.asignacion.tipo_texto}</Insignia>}
        {c.asignacion?.vencida && <Insignia clase="bg-red-100 text-red-800">Fecha sugerida vencida</Insignia>}
        {c.origen === "nomira" && <Insignia>Curso de Nomira</Insignia>}
        <InsigniaAcceso c={c} />
        {pr.estado === "completado" && <Insignia clase="bg-emerald-100 text-emerald-800">Completado</Insignia>}
        {c.aviso_vigencia && <Insignia clase="bg-amber-100 text-amber-800">Revisar vigencia</Insignia>}
      </div>
      <Link href={`/academia/cursos/${c.id}`} className="text-base font-bold leading-snug text-marino hover:underline">{c.titulo}</Link>
      <Ficha c={c} />
      {!compacta && c.descripcion && <p className="mt-2 line-clamp-3 text-sm text-slate-600">{c.descripcion}</p>}
      <div className="mt-auto pt-3">
        {pr.estado !== "sin_iniciar" && <><Barra valor={pr.porcentaje} /><p className="mt-1 text-xs text-slate-500">{pr.texto}</p></>}
        {c.asignacion?.fecha_sugerida && pr.estado !== "completado" && <p className="mt-1 text-xs text-slate-500">Terminar antes del {fecha(c.asignacion.fecha_sugerida)}</p>}
        <Link href={bloqueado ? `/academia/cursos/${c.id}` : destino} className={`${pr.estado === "completado" || bloqueado ? "btn-sec" : "btn-turquesa"} mt-3 w-full`}>{boton}</Link>
      </div>
    </article>
  );
}

/** Insignia de acceso de un curso de Nomira con costo: precio con IVA o «Contratado». */
export function InsigniaAcceso({ c }: { c: any }) {
  if (c.acceso?.tipo !== "pago") return null;
  return c.acceso.tiene_acceso
    ? <Insignia clase="bg-emerald-100 text-emerald-800">Contratado</Insignia>
    : <Insignia clase="bg-amber-100 text-amber-900">Con costo · {mxn(c.acceso.precio.total)}</Insignia>;
}

const COLOR_PLATAFORMA: Record<string, string> = { zoom: "bg-blue-100 text-blue-800", meet: "bg-emerald-100 text-emerald-800",
  teams: "bg-indigo-100 text-indigo-800", webex: "bg-sky-100 text-sky-800", otra: "bg-slate-100 text-slate-700" };

/** Sesión en vivo: plataforma reconocida (Zoom, Meet, Teams…), botón «Unirse» (se activa 15 min antes) y calendario. */
export function SesionEnVivo({ s }: { s: any }) {
  const [error, setError] = useState("");
  return (
    <div className="rounded-xl border border-crema-300 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <b className="text-marino">{s.titulo}</b>
        {s.plataforma && <Insignia clase={COLOR_PLATAFORMA[s.plataforma.clave]}>{s.plataforma.nombre}</Insignia>}
        {s.terminada && <Insignia>Terminada</Insignia>}
      </div>
      <p className="text-xs text-slate-500">{fechaHora(s.inicio)} · {s.duracion_min} min</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {s.enlace && !s.terminada && (s.unirse_activo
          ? <a className="btn-turquesa py-1.5 text-xs" href={s.enlace} target="_blank" rel="noopener noreferrer">Unirse ahora</a>
          : <span className="btn-sec cursor-not-allowed py-1.5 text-xs opacity-60" title="El botón se activa 15 minutos antes">Unirse (15 min antes)</span>)}
        {!s.terminada && <a className="btn-sec py-1.5 text-xs" href={s.google_calendar} target="_blank" rel="noopener noreferrer">Google Calendar</a>}
        {!s.terminada && <button className="btn-sec py-1.5 text-xs" onClick={() => api.descargar(`/academia/sesiones/${s.id}/calendario.ics`, "sesion.ics").catch((e) => setError(e.message))}>Outlook / Apple (.ics)</button>}
        {s.grabacion_url && <a className="btn-sec py-1.5 text-xs" href={s.grabacion_url} target="_blank" rel="noopener noreferrer">Ver grabación</a>}
      </div>
      {error && <p className="mt-1 text-xs text-red-700">{error}</p>}
    </div>
  );
}

/** Reproductor SCORM: el paquete corre en un iframe aislado (sin acceso a la sesión de Nomira) y
 *  avisa su avance por postMessage; aquí se guarda en el servidor. */
export function ReproductorScorm({ leccionId, scorm, onAvance }: { leccionId: number; scorm: any; onAvance?: (r: any) => void }) {
  const marco = useRef<HTMLIFrameElement>(null);
  const [estado, setEstado] = useState<string>(scorm.estado);
  useEffect(() => {
    let pendiente: any = null, temporizador: any = null;
    const guardar = () => {
      if (!pendiente) return;
      const datos = pendiente; pendiente = null;
      api.put(`/academia/lecciones/${leccionId}/scorm`, { datos }).then((r) => { setEstado(r.estado); onAvance?.(r); }).catch(() => {});
    };
    const oir = (ev: MessageEvent) => {
      if (ev.source !== marco.current?.contentWindow || !ev.data || ev.data.nomiraScorm !== 1) return;
      pendiente = ev.data.datos;
      clearTimeout(temporizador);
      temporizador = setTimeout(guardar, ev.data.fin ? 0 : 800);
    };
    window.addEventListener("message", oir);
    return () => { window.removeEventListener("message", oir); clearTimeout(temporizador); guardar(); };
  }, [leccionId, onAvance]);
  return (
    <div>
      <iframe ref={marco} title="Contenido SCORM" src={scorm.url} sandbox="allow-scripts allow-forms allow-popups allow-modals allow-downloads"
        className="h-[70vh] min-h-[420px] w-full rounded-xl border border-crema-300 bg-white" allow="fullscreen; autoplay" />
      <p className="mt-1 text-xs text-slate-500">Paquete SCORM {scorm.version} · estado: {estado}{scorm.calificacion != null ? ` · calificación ${scorm.calificacion}` : ""}. Su avance se guarda solo.</p>
    </div>
  );
}
