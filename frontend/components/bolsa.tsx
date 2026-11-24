"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api, mxn } from "@/lib/api";

export const ESTADO_VACANTE: Record<string, [string, string]> = {
  borrador: ["Borrador", "bg-slate-100 text-slate-600"], publicada: ["Publicada", "bg-emerald-100 text-emerald-800"],
  pausada: ["Pausada", "bg-amber-100 text-amber-800"], cerrada: ["Cerrada", "bg-slate-200 text-slate-600"],
};
export const ESTADO_PRUEBA: Record<string, [string, string]> = {
  enviada: ["Sin empezar", "bg-slate-100 text-slate-600"], en_curso: ["Contestando", "bg-amber-100 text-amber-800"],
  terminada: ["Terminada", "bg-emerald-100 text-emerald-800"], vencida: ["Vencida", "bg-slate-200 text-slate-500"], cancelada: ["Cancelada", "bg-slate-200 text-slate-500"],
};

export function sueldo(v: any) {
  if (!v.sueldo_min && !v.sueldo_max) return null;
  if (v.sueldo_min && v.sueldo_max) return `${mxn(v.sueldo_min)} a ${mxn(v.sueldo_max)} al mes`;
  return `${v.sueldo_min ? "Desde " + mxn(v.sueldo_min) : "Hasta " + mxn(v.sueldo_max)} al mes`;
}

export async function copiar(texto: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(texto); return true; } catch { return false; }
}

const VACIA = { titulo: "", area: "laboral", puesto: "abogado", jornada: "completa", modalidad: "presencial", estado_republica: "", ciudad: "",
  sueldo_min: "", sueldo_max: "", mostrar_sueldo: true, descripcion: "", requisitos: "", ofrecemos: "", en_portal: true, pruebas: [] as string[] };

export function FormVacante({ cfg, vacante, onCerrar, onListo }: { cfg: any; vacante?: any; onCerrar: () => void; onListo: (v: any) => void }) {
  const [f, setF] = useState<any>(vacante ? { ...VACIA, ...vacante, estado_republica: vacante.estado_republica || "", ciudad: vacante.ciudad || "",
    sueldo_min: vacante.sueldo_min || "", sueldo_max: vacante.sueldo_max || "", requisitos: vacante.requisitos || "", ofrecemos: vacante.ofrecemos || "" } : VACIA);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    const cuerpo = { ...f, estado_republica: f.estado_republica || null, sueldo_min: f.sueldo_min || null, sueldo_max: f.sueldo_max || null };
    for (const k of ["id", "codigo", "estado", "url", "creado_en", "publicada_en", "cerrada_en", "candidatos", "nuevos", "area_texto", "puesto_texto", "jornada_texto", "modalidad_texto"]) delete cuerpo[k];
    try { onListo(vacante ? await api.put(`/bolsa/vacantes/${vacante.id}`, cuerpo) : await api.post("/bolsa/vacantes", cuerpo)); }
    catch (er: any) { setError(er.message); } finally { setEnviando(false); }
  }
  const sel = (k: string, etiqueta: string, ops: Record<string, string>) => (
    <label className="block"><span className="etiqueta">{etiqueta}</span>
      <select className="campo" value={f[k]} onChange={pon(k)}>{Object.entries(ops).map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>);
  return (
    <Modal titulo={vacante ? "Editar vacante" : "Nueva vacante"} onCerrar={onCerrar} ancho="max-w-3xl">
      <form className="space-y-4" onSubmit={guardar}>
        <label className="block"><span className="etiqueta">Título del puesto</span>
          <input className="campo" value={f.titulo} onChange={pon("titulo")} placeholder="Ej. Abogado(a) litigante en materia laboral" required minLength={3} maxLength={200} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          {sel("area", "Materia", cfg.areas)}{sel("puesto", "Tipo de puesto", cfg.puestos)}
          {sel("jornada", "Jornada", cfg.jornadas)}{sel("modalidad", "Modalidad", cfg.modalidades)}
          <label className="block"><span className="etiqueta">Estado</span>
            <select className="campo" value={f.estado_republica} onChange={pon("estado_republica")}>
              <option value="">{f.modalidad === "remoto" ? "— Cualquiera (remoto) —" : "— Elija —"}</option>
              {cfg.estados_mx.map((e: string) => <option key={e}>{e}</option>)}</select></label>
          <label className="block"><span className="etiqueta">Ciudad o alcaldía</span><input className="campo" value={f.ciudad} onChange={pon("ciudad")} maxLength={120} /></label>
          <label className="block"><span className="etiqueta">Sueldo mensual desde</span><input className="campo" inputMode="decimal" value={f.sueldo_min} onChange={pon("sueldo_min")} placeholder="$" /></label>
          <label className="block"><span className="etiqueta">Sueldo mensual hasta</span><input className="campo" inputMode="decimal" value={f.sueldo_max} onChange={pon("sueldo_max")} placeholder="$" /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.mostrar_sueldo} onChange={pon("mostrar_sueldo")} /> Mostrar el sueldo en la publicación</label>
        <label className="block"><span className="etiqueta">¿Qué hará la persona?</span>
          <textarea className="campo min-h-28" value={f.descripcion} onChange={pon("descripcion")} required minLength={20} maxLength={8000} /></label>
        <label className="block"><span className="etiqueta">Requisitos (conocimientos, experiencia, cédula…)</span>
          <textarea className="campo min-h-20" value={f.requisitos} onChange={pon("requisitos")} maxLength={5000} /></label>
        <label className="block"><span className="etiqueta">Ofrecemos</span>
          <textarea className="campo min-h-20" value={f.ofrecemos} onChange={pon("ofrecemos")} maxLength={5000} placeholder="Prestaciones, horario, capacitación…" /></label>
        <p className="rounded-lg bg-crema/60 px-3 py-2 text-xs text-slate-600">Por ley no se puede pedir edad, sexo, estado civil, apariencia ni otros datos que discriminen. Nomira avisa si encuentra alguno.</p>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.en_portal} onChange={pon("en_portal")} /> Publicar también en la bolsa de trabajo de Nomira (nomirasoft.com/empleos)</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={enviando}>{enviando ? "Guardando…" : vacante ? "Guardar cambios" : "Guardar borrador"}</button></div>
      </form>
    </Modal>
  );
}

export function EnviarPruebas({ candidato, catalogo, onCerrar, onListo }: { candidato: any; catalogo: any; onCerrar: () => void; onListo: () => void }) {
  const [elegidas, setElegidas] = useState<string[]>([]);
  const [porCorreo, setPorCorreo] = useState(true);
  const [res, setRes] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);
  const todas = [...catalogo.nomira, ...catalogo.propias.filter((p: any) => p.activa)];
  const grupos: Record<string, any[]> = {};
  for (const p of todas) (grupos[p.categoria] ||= []).push(p);
  async function enviar() {
    setError(""); setEnviando(true);
    try { setRes(await api.post(`/bolsa/candidatos/${candidato.id}/pruebas`, { pruebas: elegidas, por_correo: porCorreo })); onListo(); }
    catch (e: any) { setError(e.message); } finally { setEnviando(false); }
  }
  const mensaje = res ? `Hola ${candidato.nombre.split(" ")[0]}, te comparto las pruebas de tu postulación (cada enlace vence en 7 días):\n` +
    res.enlaces.map((e: any) => `• ${e.nombre}: ${e.url}`).join("\n") : "";
  return (
    <Modal titulo={`Enviar pruebas a ${candidato.nombre}`} onCerrar={onCerrar} ancho="max-w-2xl">
      {!res ? <div className="space-y-4">
        {Object.entries(grupos).map(([g, ps]) => (
          <fieldset key={g}><legend className="text-xs font-bold uppercase tracking-wide text-slate-500">{g}</legend>
            <div className="mt-1 grid gap-2 sm:grid-cols-2">{ps.map((p: any) => (
              <label key={p.clave} className={`flex cursor-pointer gap-2 rounded-lg border p-3 text-sm ${elegidas.includes(p.clave) ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
                <input type="checkbox" checked={elegidas.includes(p.clave)} onChange={(e) => setElegidas(e.target.checked ? [...elegidas, p.clave] : elegidas.filter((x) => x !== p.clave))} />
                <span><b className="text-marino">{p.nombre}</b><span className="block text-xs text-slate-500">{p.preguntas} preguntas{p.minutos ? ` · ${p.minutos} min` : ""}</span></span>
              </label>))}</div></fieldset>))}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={porCorreo} onChange={(e) => setPorCorreo(e.target.checked)} /> Mandar los enlaces a {candidato.email}</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={!elegidas.length || enviando} onClick={enviar}>{enviando ? "Creando…" : `Crear ${elegidas.length || ""} enlace${elegidas.length === 1 ? "" : "s"}`}</button></div>
      </div> : <div className="space-y-3">
        <Aviso tipo="ok">{res.correo_enviado ? `Listo. Se enviaron los enlaces a ${candidato.email}.` : "Listo. Copia los enlaces y mándalos a la persona."}</Aviso>
        {porCorreo && !res.correo_disponible && <Aviso tipo="info">El envío de correos de Nomira no está configurado todavía; usa WhatsApp o copia el texto.</Aviso>}
        <ul className="space-y-1 text-sm">{res.enlaces.map((e: any) => <li key={e.id}><b>{e.nombre}:</b> <span className="break-all text-slate-600">{e.url}</span></li>)}</ul>
        <Aviso tipo="ok">{ok}</Aviso>
        <div className="flex flex-wrap justify-end gap-2">
          <button className="btn-sec" onClick={async () => setOk((await copiar(mensaje)) ? "Texto copiado." : "No se pudo copiar.")}>Copiar texto</button>
          {candidato.telefono && <a className="btn-sec" target="_blank" rel="noopener noreferrer"
            href={`https://wa.me/${candidato.telefono.replace(/\D/g, "").replace(/^(\d{10})$/, "52$1")}?text=${encodeURIComponent(mensaje)}`}>Mandar por WhatsApp</a>}
          <button className="btn-turquesa" onClick={onCerrar}>Terminar</button></div>
      </div>}
    </Modal>
  );
}

const COLOR_NIVEL: Record<string, string> = { alto: "bg-turquesa", medio: "bg-marino/60", bajo: "bg-amber-500" };

export function Resultado({ id, onCerrar }: { id: number; onCerrar: () => void }) {
  const [a, setA] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`/bolsa/aplicaciones/${id}`).then(setA).catch((e) => setError(e.message)); }, [id]);
  const r = a?.resultado;
  return (
    <Modal titulo={a ? `Resultado: ${a.nombre}` : "Resultado"} onCerrar={onCerrar} ancho="max-w-2xl">
      <Aviso>{error}</Aviso>
      {a && !r && <p className="text-sm text-slate-600">La persona todavía no termina esta prueba.</p>}
      {r?.tipo === "perfil" && <div className="space-y-3">
        {r.factores.map((f: any) => (
          <div key={f.clave}>
            <div className="flex justify-between text-sm"><b className="text-marino">{f.nombre}</b><span>{f.porcentaje}%</span></div>
            <div className="mt-1 h-2 rounded-full bg-crema-300" role="img" aria-label={`${f.nombre}: ${f.porcentaje} %`}>
              <div className={`h-2 rounded-full ${COLOR_NIVEL[f.nivel] || "bg-slate-400"}`} style={{ width: `${f.porcentaje}%` }} /></div>
            <p className="mt-1 text-xs text-slate-600">{f.lectura} <span className="text-slate-400">({f.que_mide})</span></p>
          </div>))}
        <p className="rounded-lg bg-crema/60 p-3 text-xs text-slate-600">Perfil del cuestionario público IPIP de cinco factores. No es una prueba clínica ni tiene baremo mexicano: sirve para comparar candidatos y preparar preguntas de entrevista, no para decidir por sí solo.</p>
      </div>}
      {r?.tipo === "aciertos" && <div className="space-y-3">
        <p className="text-3xl font-extrabold text-marino">{r.aciertos} de {r.total} <span className="text-base font-semibold text-slate-500">({r.porcentaje ?? 0}%)</span></p>
        {r.minutos_usados != null && <p className="text-sm text-slate-600">Tardó {r.minutos_usados} minutos{r.fuera_de_tiempo ? " (más del tiempo sugerido)" : ""}.</p>}
        {r.detalle.length > 0 && <details className="text-sm"><summary className="cursor-pointer font-semibold text-turquesa-700">Ver respuesta por pregunta</summary>
          <ol className="mt-2 list-decimal space-y-2 pl-5">{r.detalle.map((d: any, i: number) => (
            <li key={i}><span className="text-slate-700">{d.pregunta}</span><span className={`block text-xs ${d.acierto ? "text-emerald-700" : "text-red-700"}`}>
              {d.acierto ? "✓ " : "✗ "}Eligió: {d.elegida ?? "sin respuesta"}{!d.acierto && ` · Correcta: ${d.correcta}`}</span></li>))}</ol></details>}
        {r.abiertas?.length > 0 && <div><h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">Respuestas abiertas (califíquelas usted)</h3>
          {r.abiertas.map((x: any, i: number) => <div key={i} className="mt-2 rounded-lg border border-crema-300 p-3 text-sm"><b>{x.pregunta}</b>
            <p className="mt-1 whitespace-pre-wrap text-slate-700">{x.respuesta || "Sin respuesta"}</p></div>)}</div>}
      </div>}
    </Modal>
  );
}

export function VistaPrueba({ clave, onCerrar }: { clave: string; onCerrar: () => void }) {
  const [p, setP] = useState<any>(null);
  useEffect(() => { api.get(`/bolsa/pruebas/ver/${encodeURIComponent(clave)}`).then(setP).catch(() => {}); }, [clave]);
  return (
    <Modal titulo={p?.nombre || "Prueba"} onCerrar={onCerrar} ancho="max-w-2xl">
      {p && <div className="space-y-3 text-sm">
        {p.instrucciones && <p className="text-slate-600">{p.instrucciones}</p>}
        <ol className="list-decimal space-y-2 pl-5">{p.preguntas.map((q: any, i: number) => (
          <li key={i}><span className="text-marino">{q.texto}</span>
            {p.tipo !== "likert" && q.opciones.length > 0 && <ul className="mt-1 text-xs text-slate-600">{q.opciones.map((o: string, j: number) =>
              <li key={j} className={j === q.correcta ? "font-semibold text-emerald-700" : ""}>{j === q.correcta ? "✓ " : "· "}{o}</li>)}</ul>}
            {p.tipo !== "likert" && !q.opciones.length && <span className="block text-xs text-slate-500">Pregunta abierta</span>}</li>))}</ol>
        {p.tipo === "likert" && <p className="text-xs text-slate-500">Cada afirmación se contesta de «Muy en desacuerdo» a «Muy de acuerdo».</p>}
      </div>}
    </Modal>
  );
}

type Preg = { texto: string; opciones: string[]; correcta: number | null };

export function EditorPrueba({ prueba, onCerrar, onListo }: { prueba?: any; onCerrar: () => void; onListo: () => void }) {
  const [f, setF] = useState<{ nombre: string; instrucciones: string; minutos: string; preguntas: Preg[] }>({
    nombre: prueba?.nombre || "", instrucciones: prueba?.instrucciones || "", minutos: prueba?.minutos ? String(prueba.minutos) : "",
    preguntas: prueba?.preguntas?.map((q: any) => ({ texto: q.texto, opciones: q.opciones || [], correcta: q.correcta ?? null })) || [{ texto: "", opciones: ["", ""], correcta: 0 }],
  });
  const [error, setError] = useState("");
  const pq = (i: number, cambio: Partial<Preg>) => setF({ ...f, preguntas: f.preguntas.map((q, j) => (j === i ? { ...q, ...cambio } : q)) });
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    const cuerpo = { nombre: f.nombre, instrucciones: f.instrucciones || null, minutos: f.minutos ? Number(f.minutos) : null,
      preguntas: f.preguntas.map((q) => ({ texto: q.texto, opciones: q.opciones.filter((o) => o.trim()), correcta: q.opciones.length ? q.correcta : null })) };
    try { if (prueba?.id) await api.put(`/bolsa/pruebas/propias/${prueba.id}`, cuerpo); else await api.post("/bolsa/pruebas/propias", cuerpo); onListo(); }
    catch (er: any) { setError(er.message); }
  }
  return (
    <Modal titulo={prueba?.id ? "Editar prueba" : "Nueva prueba del despacho"} onCerrar={onCerrar} ancho="max-w-3xl">
      <form className="space-y-4" onSubmit={guardar}>
        <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
          <label className="block"><span className="etiqueta">Nombre</span><input className="campo" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} required minLength={3} maxLength={150} /></label>
          <label className="block"><span className="etiqueta">Minutos sugeridos</span><input className="campo" inputMode="numeric" value={f.minutos} onChange={(e) => setF({ ...f, minutos: e.target.value.replace(/\D/g, "") })} /></label></div>
        <label className="block"><span className="etiqueta">Instrucciones para la persona</span><textarea className="campo" value={f.instrucciones} onChange={(e) => setF({ ...f, instrucciones: e.target.value })} maxLength={3000} /></label>
        <ol className="space-y-3">{f.preguntas.map((q, i) => (
          <li key={i} className="rounded-lg border border-crema-300 p-3">
            <div className="flex items-start gap-2"><span className="mt-2 text-sm font-bold text-slate-500">{i + 1}.</span>
              <textarea className="campo" aria-label={`Pregunta ${i + 1}`} value={q.texto} onChange={(e) => pq(i, { texto: e.target.value })} required minLength={3} />
              <button type="button" className="text-xs text-slate-500 underline" onClick={() => setF({ ...f, preguntas: f.preguntas.filter((_, j) => j !== i) })} disabled={f.preguntas.length === 1}>Quitar</button></div>
            {q.opciones.length > 0 ? <div className="mt-2 space-y-1 pl-6">
              {q.opciones.map((o, j) => (
                <div key={j} className="flex items-center gap-2">
                  <input type="radio" name={`c${i}`} checked={q.correcta === j} onChange={() => pq(i, { correcta: j })} aria-label={`Opción ${j + 1} es la correcta`} />
                  <input className="campo py-1" value={o} aria-label={`Pregunta ${i + 1}, opción ${j + 1}`} onChange={(e) => pq(i, { opciones: q.opciones.map((x, k) => (k === j ? e.target.value : x)) })} />
                  {q.opciones.length > 2 && <button type="button" className="text-xs text-slate-500" onClick={() => pq(i, { opciones: q.opciones.filter((_, k) => k !== j), correcta: 0 })} aria-label="Quitar opción">✕</button>}
                </div>))}
              <div className="flex gap-3 text-xs">{q.opciones.length < 6 && <button type="button" className="text-turquesa-700 underline" onClick={() => pq(i, { opciones: [...q.opciones, ""] })}>+ Opción</button>}
                <button type="button" className="text-slate-500 underline" onClick={() => pq(i, { opciones: [], correcta: null })}>Hacerla abierta</button></div>
              <p className="text-xs text-slate-500">Marque con el círculo la respuesta correcta.</p>
            </div> : <p className="mt-2 pl-6 text-xs text-slate-500">Pregunta abierta: la persona escribe y usted la califica. <button type="button" className="text-turquesa-700 underline" onClick={() => pq(i, { opciones: ["", ""], correcta: 0 })}>Hacerla de opción múltiple</button></p>}
          </li>))}</ol>
        <button type="button" className="btn-sec" onClick={() => setF({ ...f, preguntas: [...f.preguntas, { texto: "", opciones: ["", ""], correcta: 0 }] })}>+ Pregunta</button>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar prueba</button></div>
      </form>
    </Modal>
  );
}

export function Premium({ texto }: { texto: string }) {
  return (
    <div className="rounded-xl border border-turquesa/40 bg-turquesa-50 p-4 text-sm text-marino">
      <p className="font-semibold">Pruebas psicométricas · versión premium</p>
      <p className="mt-1 text-slate-700">{texto}</p>
      <Link href="/organizacion" className="mt-2 inline-block font-semibold text-turquesa-700 underline">Ver cómo contratarlas</Link>
    </div>
  );
}
