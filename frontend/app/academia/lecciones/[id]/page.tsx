"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AcademiaShell, Barra, ReproductorScorm } from "@/components/academia";
import { Aviso } from "@/components/ui";
import { api, fecha } from "@/lib/api";

/** Lección: video, sesión, lectura, material, recursos y pregunta de comprobación. Guarda solo dónde se quedó. */
export default function Leccion() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [l, setL] = useState<any>(null);
  const [error, setError] = useState("");
  const [resp, setResp] = useState<number | null>(null);
  const [res, setRes] = useState<any>(null);
  const [guardado, setGuardado] = useState("");
  const [fin, setFin] = useState<any>(null);
  const ultima = useRef(0);
  useEffect(() => {
    setL(null); setRes(null); setResp(null); setFin(null);
    api.get(`/academia/lecciones/${id}`).then((x) => {
      setL(x);
      if (x.actividad?.respuesta !== undefined) { setResp(x.actividad.respuesta); setRes({ correcta: x.actividad.correcta, respuesta_correcta: x.actividad.respuesta_correcta, explicacion: x.actividad.explicacion }); }
      if (x.posicion > 0) setTimeout(() => window.scrollTo({ top: x.posicion }), 150);  // retoma donde se quedó
    }).catch((e) => setError(e.message));
  }, [id]);
  // Guardado automático de la posición (cada vez que se detiene el desplazamiento)
  useEffect(() => {
    if (!l || l.vista_previa) return;
    let t: any;
    const guardar = () => {
      const pos = Math.round(window.scrollY);
      if (Math.abs(pos - ultima.current) < 80) return;
      ultima.current = pos;
      api.put(`/academia/lecciones/${id}/avance`, { posicion: pos }).then(() => setGuardado("Avance guardado")).catch(() => {});
    };
    const alMover = () => { clearTimeout(t); t = setTimeout(guardar, 1200); };
    window.addEventListener("scroll", alMover, { passive: true });
    return () => { window.removeEventListener("scroll", alMover); clearTimeout(t); };
  }, [l, id]);
  async function responder() {
    if (resp === null) return;
    try { setRes(await api.post(`/academia/lecciones/${id}/actividad`, { respuesta: resp })); } catch (e: any) { setError(e.message); }
  }
  async function completar() {
    setError("");
    try {
      const r = await api.post(`/academia/lecciones/${id}/completar`);
      if (r.siguiente_id && !r.completado) router.push(`/academia/lecciones/${r.siguiente_id}`);
      else if (r.ir_a_cuestionario) router.push(`/academia/cursos/${l.curso_id}/cuestionario`);
      else if (l.siguiente_id) router.push(`/academia/lecciones/${l.siguiente_id}`);
      else setFin(r);
    } catch (e: any) { setError(e.message); }
  }
  if (!l) return <AcademiaShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AcademiaShell>;
  return (
    <AcademiaShell>
      <div className="mx-auto max-w-3xl">
        <Link href={`/academia/cursos/${l.curso_id}`} className="text-sm font-semibold text-turquesa-700 hover:underline">← {l.curso}</Link>
        <div className="mt-3"><Barra valor={l.progreso.porcentaje} /><p className="mt-1 text-xs text-slate-500">Lección {l.numero} de {l.total} · {l.progreso.texto}{guardado && !l.vista_previa ? ` · ${guardado}` : ""}</p></div>
        {l.vista_previa && <div className="mt-3"><Aviso tipo="info">Vista previa de un curso no publicado: el avance no se guarda.</Aviso></div>}
        {l.aviso_vigencia && <div className="mt-3"><Aviso tipo="alerta">{l.aviso_vigencia}</Aviso></div>}
        <p className="mt-5 text-xs font-semibold uppercase tracking-wider text-slate-500">{l.modulo}</p>
        <h1 className="text-3xl font-extrabold text-marino">{l.titulo}</h1>
        <div className="mt-5 space-y-5">
          {l.scorm && <ReproductorScorm leccionId={l.id} scorm={l.scorm} onAvance={(r) => {
            if (r.leccion_completada && !l.completada) setL({ ...l, completada: true });
            if (r.curso_completado) setGuardado("¡Curso completado! Su diploma ya está disponible en la página del curso");
          }} />}
          {l.video_subido && <video className="aspect-video w-full rounded-2xl bg-black" controls preload="metadata" controlsList="nodownload" src={l.video_subido.url}
            onLoadedMetadata={(e) => { if (l.posicion > 0 && l.posicion < (e.currentTarget.duration || 0)) e.currentTarget.currentTime = l.posicion; }}>
            Su navegador no puede reproducir este video.</video>}
          {l.video_url && (l.video_embebido
            ? <div className="aspect-video overflow-hidden rounded-2xl bg-black"><iframe className="h-full w-full" src={l.video_embebido} title={`Video: ${l.titulo}`} allow="encrypted-media; picture-in-picture; fullscreen" referrerPolicy="strict-origin-when-cross-origin" /></div>
            : <a className="btn-sec" href={l.video_url} target="_blank" rel="noopener noreferrer">Abrir el video en su sitio</a>)}
          {l.transcripcion && <details className="tarjeta p-4 text-sm"><summary className="cursor-pointer font-semibold text-marino">Transcripción del video</summary><p className="mt-2 whitespace-pre-line text-slate-700">{l.transcripcion}</p></details>}
          {l.sesion_url && <div className="tarjeta flex flex-wrap items-center justify-between gap-2 p-4 text-sm"><span>Esta lección incluye una sesión en vivo o grabada{l.sesion_plataforma && l.sesion_plataforma.clave !== "otra" ? ` en ${l.sesion_plataforma.nombre}` : ""}.</span>
            <a className="btn-turquesa" href={l.sesion_url} target="_blank" rel="noopener noreferrer">{l.sesion_plataforma && l.sesion_plataforma.clave !== "otra" ? `Abrir en ${l.sesion_plataforma.nombre}` : "Abrir la sesión"}</a></div>}
          {l.texto && <div className="whitespace-pre-line text-[17px] leading-relaxed text-slate-800">{l.texto}</div>}
          {l.archivo && <div className="tarjeta flex flex-wrap items-center justify-between gap-2 p-4 text-sm"><span>Material: <b>{l.archivo.nombre}</b> ({l.archivo.formato.toUpperCase()}, {Math.ceil(l.archivo.tamano / 1024)} KB)</span>
            <button className="btn-sec" onClick={() => api.descargar(`/academia/lecciones/${l.id}/archivo`, l.archivo.nombre).catch((e) => setError(e.message))}>Descargar</button></div>}
          {l.recursos.length > 0 && <section className="tarjeta p-4 text-sm"><h2 className="mb-1 font-semibold text-marino">Recursos y enlaces</h2>
            <ul className="list-disc space-y-1 pl-5">{l.recursos.map((x: any, i: number) => <li key={i}><a className="text-turquesa-700 underline" href={x.url} target="_blank" rel="noopener noreferrer">{x.titulo}</a></li>)}</ul></section>}
          {l.actividad && (
            <section className="tarjeta border-turquesa/40 p-5">
              <h2 className="font-semibold text-marino">Pregunta de comprobación</h2>
              <p className="mt-1 text-sm text-slate-800">{l.actividad.pregunta}</p>
              <div className="mt-3 space-y-2">
                {l.actividad.opciones.map((o: string, i: number) => {
                  const marca = res ? (i === res.respuesta_correcta ? "border-emerald-400 bg-emerald-50" : i === resp ? "border-red-300 bg-red-50" : "border-crema-300") : resp === i ? "border-turquesa bg-turquesa-50" : "border-crema-300";
                  return <label key={i} className={`flex cursor-pointer items-center gap-2 rounded-xl border p-3 text-sm ${marca}`}>
                    <input type="radio" name="actividad" className="accent-turquesa" checked={resp === i} disabled={!!res} onChange={() => setResp(i)} />{o}</label>;
                })}
              </div>
              {res ? <p className={`mt-3 text-sm ${res.correcta ? "text-emerald-800" : "text-amber-900"}`}><b>{res.correcta ? "¡Correcto!" : "No es la respuesta esperada."}</b> {res.explicacion}</p>
                : <button className="btn-sec mt-3" disabled={resp === null} onClick={responder}>Responder</button>}
            </section>)}
        </div>
        <Aviso>{error}</Aviso>
        {fin ? (
          <section className="tarjeta mt-6 border-emerald-300 bg-emerald-50 p-5 text-center">
            <h2 className="text-xl font-bold text-emerald-900">{fin.completado ? "¡Terminó el curso!" : "Lección completada"}</h2>
            {fin.completado && <p className="mt-1 text-sm text-emerald-900">Ya puede descargar su diploma.</p>}
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {fin.completado && <button className="btn-turquesa" onClick={() => api.descargar(`/academia/constancias/${fin.avance_id}`, "diploma.pdf")}>Descargar diploma</button>}
              <Link className="btn-sec" href={`/academia/cursos/${l.curso_id}`}>Volver al curso</Link>
              <Link className="btn-sec" href="/academia">Mi aprendizaje</Link>
            </div>
          </section>
        ) : (
          <div className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t border-crema-300 pt-4">
            {l.anterior_id ? <Link className="btn-sec" href={`/academia/lecciones/${l.anterior_id}`}>← Anterior</Link> : <span />}
            {l.vista_previa ? (l.siguiente_id && <Link className="btn-sec" href={`/academia/lecciones/${l.siguiente_id}`}>Siguiente →</Link>)
              : <button className="btn-turquesa px-5 py-2.5 text-base" disabled={!!l.actividad && !res} onClick={completar}>
                {l.completada ? (l.siguiente_id ? "Siguiente lección →" : "Terminar") : l.siguiente_id ? "Completar y continuar →" : "Completar lección"}</button>}
          </div>)}
        {l.actividad && !res && !l.vista_previa && <p className="mt-2 text-right text-xs text-slate-500">Responda la pregunta para continuar.</p>}
        <p className="mt-6 text-xs text-slate-400">Lección actualizada el {fecha(l.actualizado_en)}.</p>
      </div>
    </AcademiaShell>
  );
}
