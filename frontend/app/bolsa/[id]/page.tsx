"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { ESTADO_PRUEBA, ESTADO_VACANTE, EnviarPruebas, FormVacante, Premium, Resultado, copiar, sueldo } from "@/components/bolsa";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const fecha = (s: string) => new Date(s).toLocaleDateString("es-MX", { day: "numeric", month: "short" });

export default function Vacante() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<any>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [cat, setCat] = useState<any>(null);
  const [filtro, setFiltro] = useState("activos");
  const [dialogo, setDialogo] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const cargar = useCallback(() => api.get(`/bolsa/vacantes/${id}`).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); api.get("/bolsa/config").then(setCfg).catch(() => {}); api.get("/bolsa/pruebas").then(setCat).catch(() => {}); }, [cargar]);
  async function accion(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await f(); setOk(msg); await cargar(); } catch (e: any) { setError(e.message); }
  }
  if (!d || !cfg) return <Shell><Aviso>{error}</Aviso></Shell>;
  const v = d.vacante;
  const lista = d.candidatos.filter((c: any) => filtro === "todos" || (filtro === "activos" ? c.etapa !== "descartado" : c.etapa === filtro));
  const actual = dialogo?.tipo === "candidato" ? d.candidatos.find((c: any) => c.id === dialogo.id) : null;
  return (
    <Shell>
      <Link href="/bolsa" className="text-sm font-semibold text-turquesa-700">← Bolsa de trabajo</Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">{v.titulo}</h1>
          <p className="mt-1 text-sm text-slate-600">{v.puesto_texto} · {v.area_texto} · {v.jornada_texto} · {v.modalidad_texto}{v.estado_republica ? ` · ${v.ciudad ? v.ciudad + ", " : ""}${v.estado_republica}` : ""}{sueldo(v) ? ` · ${sueldo(v)}` : ""}</p>
          <p className="mt-2"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_VACANTE[v.estado][1]}`}>{ESTADO_VACANTE[v.estado][0]}</span>
            {v.estado === "publicada" && <span className="ml-2 text-xs text-slate-500">{v.en_portal ? "En tu página y en la bolsa de Nomira" : "Solo en tu página de empleos"}</span>}</p></div>
        {cfg.puede_editar && <div className="flex flex-wrap gap-2">
          {v.estado === "publicada" && <button className="btn-turquesa" onClick={async () => setOk((await copiar(v.url)) ? "Enlace copiado." : v.url)}>Copiar enlace</button>}
          {(v.estado === "borrador" || v.estado === "pausada") && <button className="btn-turquesa" onClick={() => accion(() => api.post(`/bolsa/vacantes/${v.id}/estado`, { estado: "publicada" }), "Vacante publicada.")}>Publicar</button>}
          {v.estado === "publicada" && <button className="btn-sec" onClick={() => accion(() => api.post(`/bolsa/vacantes/${v.id}/estado`, { estado: "pausada" }), "Vacante pausada: ya no recibe postulaciones.")}>Pausar</button>}
          {v.estado !== "cerrada" && <button className="btn-sec" onClick={() => setDialogo({ tipo: "editar" })}>Editar</button>}
          {v.estado !== "cerrada" && v.estado !== "borrador" && <button className="btn-sec" onClick={() => accion(() => api.post(`/bolsa/vacantes/${v.id}/estado`, { estado: "cerrada" }), "Vacante cerrada.")}>Cerrar vacante</button>}
          {cfg.es_admin && <button className="btn-sec text-red-700" onClick={() => setDialogo({ tipo: "borrar" })}>Eliminar</button>}
        </div>}
      </div>
      <div className="my-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      <section className="tarjeta overflow-hidden" aria-label="Candidatos">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-4 py-3">
          <h2 className="font-semibold text-marino">Candidatos ({d.candidatos.length})</h2>
          <select className="campo w-auto py-1 text-sm" aria-label="Filtrar candidatos" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="activos">Activos</option><option value="todos">Todos</option>
            {Object.entries(cfg.etapas).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select>
        </div>
        {!lista.length ? <p className="p-6 text-center text-sm text-slate-500">{d.candidatos.length ? "Nadie en esta etapa." : v.estado === "publicada" ? "Aún no hay postulaciones. Comparte el enlace de la vacante." : "Publica la vacante para empezar a recibir candidatos."}</p> :
          <table className="w-full text-sm"><thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
            <th className="px-4 py-2">Nombre</th><th className="px-4 py-2">Experiencia</th><th className="px-4 py-2">Pruebas</th><th className="px-4 py-2">Etapa</th></tr></thead>
            <tbody className="divide-y divide-crema-200">{lista.map((c: any) => (
              <tr key={c.id}>
                <td className="px-4 py-3"><button className="text-left font-semibold text-marino hover:underline" onClick={() => setDialogo({ tipo: "candidato", id: c.id })}>{c.nombre}</button>
                  <span className="block text-xs text-slate-500">{fecha(c.creado_en)}{c.calificacion ? ` · ${"★".repeat(c.calificacion)}` : ""}{c.etapa === "nuevo" ? " · Nuevo" : ""}</span></td>
                <td className="px-4 py-3 text-slate-600">{c.experiencia_texto || "—"}</td>
                <td className="px-4 py-3">{c.pruebas.length ? c.pruebas.map((p: any) => (
                  <span key={p.id} className="mr-1 inline-block text-xs">{p.estado === "terminada" && p.porcentaje != null ? <b className="text-marino">{p.nombre.replace("Conocimientos: ", "")} {p.porcentaje}%</b>
                    : <span className={`rounded-full px-2 py-0.5 ${ESTADO_PRUEBA[p.estado][1]}`}>{p.nombre.replace("Conocimientos: ", "")}: {ESTADO_PRUEBA[p.estado][0]}</span>}</span>)) : <span className="text-slate-400">—</span>}</td>
                <td className="px-4 py-3">{cfg.puede_editar ? <select className="campo py-1 text-sm" aria-label={`Etapa de ${c.nombre}`} value={c.etapa}
                  onChange={(e) => accion(() => api.put(`/bolsa/candidatos/${c.id}`, { etapa: e.target.value }), "Etapa actualizada.")}>
                  {Object.entries(cfg.etapas).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select> : c.etapa_texto}</td>
              </tr>))}</tbody></table>}
      </section>

      {dialogo?.tipo === "editar" && <FormVacante cfg={cfg} vacante={v} onCerrar={() => setDialogo(null)} onListo={() => { setDialogo(null); setOk("Vacante actualizada."); cargar(); }} />}
      {dialogo?.tipo === "borrar" && <ConfirmarEliminar titulo="Eliminar vacante" onCerrar={() => setDialogo(null)}
        onConfirmar={() => api.borrar(`/bolsa/vacantes/${v.id}`).then(() => { window.location.href = "/bolsa"; })}>
        Se borrarán la vacante, sus {d.candidatos.length} candidatos, sus CVs y resultados de pruebas. No se puede deshacer.</ConfirmarEliminar>}
      {actual && <FichaCandidato c={actual} cfg={cfg} cat={cat} onCerrar={() => setDialogo(null)} onCambio={cargar}
        onPruebas={() => setDialogo({ tipo: "pruebas", id: actual.id })} onResultado={(aid) => setDialogo({ tipo: "resultado", aid, id: actual.id })} />}
      {dialogo?.tipo === "pruebas" && cat && <EnviarPruebas candidato={d.candidatos.find((c: any) => c.id === dialogo.id)} catalogo={cat}
        onCerrar={() => setDialogo({ tipo: "candidato", id: dialogo.id })} onListo={cargar} />}
      {dialogo?.tipo === "resultado" && <Resultado id={dialogo.aid} onCerrar={() => setDialogo({ tipo: "candidato", id: dialogo.id })} />}
    </Shell>
  );
}

function FichaCandidato({ c, cfg, cat, onCerrar, onCambio, onPruebas, onResultado }: {
  c: any; cfg: any; cat: any; onCerrar: () => void; onCambio: () => void; onPruebas: () => void; onResultado: (id: number) => void }) {
  const [notas, setNotas] = useState(c.notas || "");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [borrar, setBorrar] = useState(false);
  async function guardar(cambio: any, msg: string) {
    setError(""); setOk("");
    try { await api.put(`/bolsa/candidatos/${c.id}`, cambio); setOk(msg); onCambio(); } catch (e: any) { setError(e.message); }
  }
  if (borrar) return <ConfirmarEliminar titulo="Borrar candidato" onCerrar={() => setBorrar(false)}
    onConfirmar={() => api.borrar(`/bolsa/candidatos/${c.id}`).then(() => { onCambio(); onCerrar(); })}>
    Se borran sus datos, su CV y sus pruebas. Úsalo si la persona pide que elimines su información.</ConfirmarEliminar>;
  return (
    <Modal titulo={c.nombre} onCerrar={onCerrar} ancho="max-w-2xl">
      <div className="space-y-4 text-sm">
        <dl className="grid grid-cols-[8rem_1fr] gap-y-1">
          <dt className="text-slate-500">Correo</dt><dd><a href={`mailto:${c.email}`} className="text-turquesa-700 underline">{c.email}</a></dd>
          {c.telefono && <><dt className="text-slate-500">Teléfono</dt><dd>{c.telefono}</dd></>}
          {c.ciudad && <><dt className="text-slate-500">Ciudad</dt><dd>{c.ciudad}</dd></>}
          {c.cedula && <><dt className="text-slate-500">Cédula</dt><dd>{c.cedula}</dd></>}
          {c.experiencia_texto && <><dt className="text-slate-500">Experiencia</dt><dd>{c.experiencia_texto}</dd></>}
        </dl>
        {c.mensaje && <p className="whitespace-pre-wrap rounded-lg bg-crema/60 p-3 text-slate-700">{c.mensaje}</p>}
        {c.cv && <button className="btn-sec" onClick={() => api.descargar(`/bolsa/candidatos/${c.id}/cv`, c.cv_nombre || "cv.pdf").catch((e) => setError(e.message))}>Descargar CV</button>}
        <div><span className="etiqueta">Calificación interna</span>
          <div className="flex gap-1" role="radiogroup" aria-label="Calificación">{[1, 2, 3, 4, 5].map((n) => (
            <button key={n} role="radio" aria-checked={c.calificacion === n} aria-label={`${n} estrellas`} disabled={!cfg.puede_editar}
              className={`text-2xl ${c.calificacion && n <= c.calificacion ? "text-amber-500" : "text-slate-300"}`}
              onClick={() => guardar({ calificacion: c.calificacion === n ? 0 : n }, "Calificación guardada.")}>★</button>))}</div></div>
        <div><div className="flex items-center justify-between"><span className="etiqueta">Pruebas</span>
          {cfg.puede_editar && cat?.premium && <button className="btn-sec text-sm" onClick={onPruebas}>Enviar pruebas</button>}</div>
          {!cat?.premium && <Premium texto="Envía pruebas de personalidad, razonamiento y conocimientos jurídicos a este candidato y compáralo con los demás." />}
          {c.pruebas.length > 0 && <ul className="mt-1 divide-y divide-crema-200">{c.pruebas.map((p: any) => (
            <li key={p.id} className="flex items-center justify-between gap-2 py-2">
              <span>{p.nombre} <span className={`ml-1 rounded-full px-2 py-0.5 text-xs ${ESTADO_PRUEBA[p.estado][1]}`}>{ESTADO_PRUEBA[p.estado][0]}</span></span>
              {p.estado === "terminada" && <button className="text-xs font-semibold text-turquesa-700 underline" onClick={() => onResultado(p.id)}>
                {p.porcentaje != null ? `${p.porcentaje}% · Ver` : "Ver resultado"}</button>}</li>))}</ul>}
        </div>
        <label className="block"><span className="etiqueta">Notas internas</span>
          <textarea className="campo min-h-20" value={notas} onChange={(e) => setNotas(e.target.value)} disabled={!cfg.puede_editar} maxLength={8000} /></label>
        <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
        <div className="flex flex-wrap justify-between gap-2">
          {cfg.es_admin ? <button className="text-xs text-red-700 underline" onClick={() => setBorrar(true)}>Borrar candidato y sus datos</button> : <span />}
          {cfg.puede_editar && <button className="btn-turquesa" onClick={() => guardar({ notas }, "Notas guardadas.")}>Guardar notas</button>}</div>
      </div>
    </Modal>
  );
}
