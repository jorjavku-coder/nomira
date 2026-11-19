"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, fecha } from "@/lib/api";

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
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-turquesa-700">Nomira Academia</p>
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
  const boton = pr.estado === "completado" ? "Ver curso" : pr.estado === "en_curso" ? "Continuar curso" : "Iniciar curso";
  const destino = pr.estado === "en_curso" && (c.ultima_leccion_id || pr.siguiente_leccion_id) ? `/academia/lecciones/${c.ultima_leccion_id || pr.siguiente_leccion_id}` : `/academia/cursos/${c.id}`;
  return (
    <article className="tarjeta flex flex-col p-4">
      <div className="mb-1 flex flex-wrap gap-1.5">
        {c.asignacion && <Insignia clase={c.asignacion.tipo === "obligatorio" ? "bg-marino text-white" : "bg-turquesa-50 text-turquesa-700"}>{c.asignacion.tipo_texto}</Insignia>}
        {c.asignacion?.vencida && <Insignia clase="bg-red-100 text-red-800">Fecha sugerida vencida</Insignia>}
        {c.origen === "nomira" && <Insignia>Curso de Nomira</Insignia>}
        {pr.estado === "completado" && <Insignia clase="bg-emerald-100 text-emerald-800">Completado</Insignia>}
        {c.aviso_vigencia && <Insignia clase="bg-amber-100 text-amber-800">Revisar vigencia</Insignia>}
      </div>
      <Link href={`/academia/cursos/${c.id}`} className="text-base font-bold leading-snug text-marino hover:underline">{c.titulo}</Link>
      <Ficha c={c} />
      {!compacta && c.descripcion && <p className="mt-2 line-clamp-3 text-sm text-slate-600">{c.descripcion}</p>}
      <div className="mt-auto pt-3">
        {pr.estado !== "sin_iniciar" && <><Barra valor={pr.porcentaje} /><p className="mt-1 text-xs text-slate-500">{pr.texto}</p></>}
        {c.asignacion?.fecha_sugerida && pr.estado !== "completado" && <p className="mt-1 text-xs text-slate-500">Terminar antes del {fecha(c.asignacion.fecha_sugerida)}</p>}
        <Link href={destino} className={`${pr.estado === "completado" ? "btn-sec" : "btn-turquesa"} mt-3 w-full`}>{boton}</Link>
      </div>
    </article>
  );
}
