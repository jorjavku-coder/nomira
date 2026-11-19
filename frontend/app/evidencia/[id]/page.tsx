"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FormAsunto } from "@/components/EvFormAsunto";
import EvVisor from "@/components/EvVisor";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha, fechaHora, mxn } from "@/lib/api";

type Pestana = "documentos" | "hechos" | "cronologia" | "matriz" | "pendientes";
const LECTURA: Record<string, [string, string]> = {
  pendiente: ["En cola", "bg-blue-100 text-blue-800"], procesando: ["Leyendo…", "bg-blue-100 text-blue-800"],
  leido: ["Leído", "bg-emerald-100 text-emerald-800"], requiere_revision: ["Requiere revisión", "bg-amber-100 text-amber-800"],
  error: ["No legible", "bg-red-100 text-red-800"],
};
const COLOR_HECHO: Record<string, string> = {
  por_revisar: "bg-amber-100 text-amber-800", confirmado: "bg-emerald-100 text-emerald-800",
  editado: "bg-turquesa-100 text-turquesa-700", descartado: "bg-slate-200 text-slate-600",
};
const COLOR_PUNTO: Record<string, string> = {
  pendiente_evidencia: "bg-slate-100 text-slate-700", respaldado: "bg-emerald-100 text-emerald-800",
  parcial: "bg-sky-100 text-sky-800", contradictorio: "bg-amber-100 text-amber-800",
};

function Pastilla({ clase, children }: { clase: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${clase}`}>{children}</span>;
}

export default function Asunto() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const sesion = useSesion();
  const editor = !!sesion && sesion.usuario.rol !== "consulta";
  const [p, setP] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [pestana, setPestana] = useState<Pestana>("documentos");
  const [visor, setVisor] = useState<any>(null);
  const [editarAsunto, setEditarAsunto] = useState(false);
  const [eliminar, setEliminar] = useState(false);
  const inicial = useRef(true);

  const cargar = useCallback(async () => {
    try {
      const d = await api.get(`/evidencia/asuntos/${id}`);
      setP(d);
      if (inicial.current) {  // primera vista: lleva a lo que requiere atención
        inicial.current = false;
        if (d.resumen.hechos.por_revisar > 0) setPestana("hechos");
      }
    } catch (e: any) { setError(e.message); }
  }, [id]);
  useEffect(() => { cargar(); }, [cargar]);
  const enProceso = !!p && p.resumen.documentos_en_proceso > 0;
  useEffect(() => {
    if (!enProceso) return;
    const t = setInterval(cargar, 2500);
    return () => clearInterval(t);
  }, [enProceso, cargar]);

  async function accion(fn: () => Promise<any>, mensaje = "") {
    setError(""); setOk("");
    try { const r = await fn(); if (mensaje) setOk(mensaje); await cargar(); return r; } catch (e: any) { setError(e.message); }
  }
  const docs = useMemo(() => Object.fromEntries((p?.documentos || []).map((d: any) => [d.id, d])), [p]);
  const verFuente = (x: any) => {
    const d = docs[x.documento_id];
    if (d) setVisor({ documento: d, pagina: x.pagina, bbox: x.bbox, fragmento: x.fragmento });
  };
  const Fuente = ({ x }: { x: any }) => {
    const d = docs[x.documento_id];
    if (!d) return <span className="text-xs font-semibold text-red-700">Sin documento fuente</span>;
    return (
      <button className="text-left text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => verFuente(x)} title="Abrir el documento en la página de origen">
        D{d.id} · {d.nombre}{x.pagina ? `, p. ${x.pagina}` : ""} ↗
      </button>
    );
  };

  if (!p) return <Shell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</Shell>;
  const a = p.asunto, r = p.resumen;
  const revisados = r.hechos.confirmado + r.hechos.editado;
  const tabs: [Pestana, string, number?][] = [
    ["documentos", "Documentos", r.documentos], ["hechos", "Hechos", r.hechos.por_revisar], ["cronologia", "Cronología", revisados],
    ["matriz", "Matriz de evidencia", p.puntos.length], ["pendientes", "Pendientes", r.pendientes_abiertos],
  ];
  return (
    <Shell>
      <Link href="/evidencia" className="text-sm text-turquesa-700 hover:underline">← Asuntos</Link>
      <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-extrabold text-marino">{a.nombre}</h1>
            {a.tipo_caso && <Pastilla clase="bg-marino-50 text-marino">{a.tipo_caso}</Pastilla>}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {[a.cliente && `Cliente: ${a.cliente}`, a.jurisdiccion, a.identificador_interno && `Ref. ${a.identificador_interno}`,
              a.responsable ? `Responsable: ${a.responsable}` : "Sin responsable"].filter(Boolean).join(" · ")}
          </p>
          {Object.keys(a.campos || {}).length > 0 && (
            <p className="mt-0.5 text-xs text-slate-500">{Object.entries(a.campos).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {editor && <button className="btn-sec" onClick={() => setEditarAsunto(true)}>Editar datos</button>}
          <button className="btn-sec" onClick={() => api.descargar(`/evidencia/asuntos/${id}/exportar/pdf`, `evidencia-${id}.pdf`).catch((e) => setError(e.message))}>Exportar PDF</button>
          <button className="btn-sec" onClick={() => api.descargar(`/evidencia/asuntos/${id}/exportar/excel`, `evidencia-${id}.xlsx`).catch((e) => setError(e.message))}>Exportar Excel</button>
          {sesion?.usuario.rol === "administrador" && <button className="btn-peligro" onClick={() => setEliminar(true)}>Eliminar</button>}
        </div>
      </div>

      <div className="my-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[
          ["Documentos", r.documentos, r.documentos_por_revisar ? `${r.documentos_por_revisar} por revisar` : r.documentos_sin_clasificar ? `${r.documentos_sin_clasificar} sin clasificar` : "", "documentos", !!r.documentos_por_revisar],
          ["Hechos por revisar", r.hechos.por_revisar, "propuestos, sin confirmar", "hechos", r.hechos.por_revisar > 0],
          ["Hechos revisados", revisados, `${r.hechos.descartado} descartados`, "cronologia", false],
          ["Posibles contradicciones", r.contradicciones, r.contradicciones ? "para revisar" : "", "cronologia", r.contradicciones > 0],
          ["Puntos sin evidencia", r.puntos.pendiente_evidencia, `de ${p.puntos.length} en la matriz`, "matriz", false],
          ["Pendientes abiertos", r.pendientes_abiertos, "", "pendientes", false],
        ].map(([t, v, nota, destino, alerta]: any) => (
          <button key={t} onClick={() => setPestana(destino)} className={`tarjeta p-4 text-left transition hover:border-turquesa ${alerta ? "border-amber-300 bg-amber-50" : ""}`}>
            <div className="etiqueta">{t}</div>
            <div className="font-marca text-2xl font-extrabold text-marino">{v}</div>
            {nota && <div className="text-xs text-slate-500">{nota}</div>}
          </button>
        ))}
      </div>

      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {enProceso && <div className="mt-2"><Aviso tipo="info">Leyendo {r.documentos_en_proceso} documento(s)… esta página se actualiza sola.</Aviso></div>}

      <div className="mb-5 mt-4 flex gap-1 overflow-x-auto border-b border-crema-300" role="tablist">
        {tabs.map(([k, t, n]) => (
          <button key={k} role="tab" aria-selected={pestana === k} onClick={() => setPestana(k)}
            className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold ${pestana === k ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>
            {t}{n ? <span className={`ml-1.5 rounded-full px-1.5 text-[11px] ${k === "hechos" ? "bg-amber-100 text-amber-800" : "bg-crema-200 text-slate-600"}`}>{n}</span> : null}
          </button>
        ))}
      </div>

      {pestana === "documentos" && <Documentos p={p} id={id} editor={editor} accion={accion} verFuente={verFuente} setError={setError} />}
      {pestana === "hechos" && <Hechos p={p} id={id} editor={editor} accion={accion} Fuente={Fuente} />}
      {pestana === "cronologia" && <Cronologia p={p} id={id} editor={editor} accion={accion} Fuente={Fuente} />}
      {pestana === "matriz" && <Matriz p={p} id={id} editor={editor} accion={accion} Fuente={Fuente} />}
      {pestana === "pendientes" && <Pendientes p={p} id={id} editor={editor} accion={accion} setError={setError} />}

      {visor && <EvVisor {...visor} onCerrar={() => setVisor(null)} />}
      {editarAsunto && <FormAsunto titulo="Datos del asunto" inicial={a} onCerrar={() => setEditarAsunto(false)}
        onGuardar={async (datos) => { await api.patch(`/evidencia/asuntos/${id}`, datos); setEditarAsunto(false); setOk("Datos actualizados."); cargar(); }} />}
      {eliminar && <EliminarAsunto nombre={a.nombre} onCerrar={() => setEliminar(false)}
        onConfirmar={async (texto) => { await api.post(`/evidencia/asuntos/${id}/eliminar`, { confirmar_nombre: texto }); router.replace("/evidencia"); }} />}
    </Shell>
  );
}

function EliminarAsunto({ nombre, onCerrar, onConfirmar }: { nombre: string; onCerrar: () => void; onConfirmar: (t: string) => Promise<any> }) {
  const [texto, setTexto] = useState("");
  const [error, setError] = useState("");
  return (
    <Modal titulo="Eliminar asunto" onCerrar={onCerrar}>
      <div className="space-y-3 text-sm">
        <p>Se borrarán el asunto, sus documentos originales, hechos, matriz y pendientes. <b>No se puede deshacer.</b></p>
        <label className="block"><span className="etiqueta">Escriba «{nombre}» para confirmar</span>
          <input className="campo" value={texto} onChange={(e) => setTexto(e.target.value)} /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2">
          <button className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn bg-red-600 text-white hover:bg-red-700" disabled={texto.trim() !== nombre}
            onClick={() => onConfirmar(texto).catch((e) => setError(e.message))}>Eliminar definitivamente</button>
        </div>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ Documentos

function Documentos({ p, id, editor, accion, verFuente, setError }: any) {
  const entrada = useRef<HTMLInputElement>(null);
  const [subida, setSubida] = useState<any[] | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [clasificar, setClasificar] = useState<any>(null);
  async function subir(lista: FileList | null) {
    if (!lista?.length) return;
    const fd = new FormData();
    Array.from(lista).forEach((f) => fd.append("archivos", f));
    setSubiendo(true);
    const r = await accion(() => api.subir(`/evidencia/asuntos/${id}/documentos`, fd));
    if (r) setSubida(r);
    setSubiendo(false);
    if (entrada.current) entrada.current.value = "";
  }
  return (
    <div className="space-y-4">
      {editor && (
        <div className="tarjeta flex flex-wrap items-center gap-3 border-2 border-dashed p-5" onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); subir(e.dataTransfer.files); }}>
          <input ref={entrada} type="file" multiple className="hidden" accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" onChange={(e) => subir(e.target.files)} />
          <button className="btn-turquesa" disabled={subiendo} onClick={() => entrada.current?.click()}>{subiendo ? "Subiendo…" : "Subir documentos"}</button>
          <span className="text-sm text-slate-500">PDF o imágenes (JPG, PNG, WebP), o arrástrelos aquí. El original se guarda sin cambios; Nomira lo lee y propone su tipo, fecha y hechos.</span>
        </div>
      )}
      {subida && <div className="space-y-1">{subida.map((s, i) => <Aviso key={i} tipo={s.aceptado ? "ok" : "alerta"}><b>{s.nombre}:</b> {s.aceptado ? "recibido; leyendo." : s.motivo}</Aviso>)}</div>}
      {p.documentos.length === 0 ? (
        <div className="tarjeta p-10 text-center text-sm text-slate-500">Aún no hay documentos en este asunto.</div>
      ) : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Ref.</th><th>Documento</th><th>Lectura</th><th>Tipo</th><th>Fecha</th><th>Hechos</th><th></th></tr></thead>
            <tbody>
              {p.documentos.map((d: any) => {
                const [txt, clase] = LECTURA[d.estado];
                return (
                  <tr key={d.id}>
                    <td className="font-mono text-xs font-semibold">D{d.id}</td>
                    <td><div className="font-semibold">{d.nombre}</div>
                      <div className="text-xs text-slate-500">{d.formato.toUpperCase()} · {d.paginas ?? "?"} pág. · {(d.tamano_bytes / 1048576).toFixed(1)} MB · {d.subido_por || "—"}, {fechaHora(d.creado_en)}</div>
                      {d.error && <div className="mt-1 max-w-md text-xs text-amber-800">{d.error}</div>}</td>
                    <td><Pastilla clase={clase}>{txt}</Pastilla></td>
                    <td>{d.tipo ? <span className="font-semibold">{d.tipo}</span>
                      : d.tipo_sugerido ? <span className="text-slate-600">{d.tipo_sugerido} <span className="text-xs text-amber-700">(sugerido)</span></span>
                        : <span className="text-slate-400">Sin clasificar</span>}</td>
                    <td className="whitespace-nowrap">{d.fecha_documento ? fecha(d.fecha_documento)
                      : d.fecha_sugerida ? <span className="text-slate-600">{fecha(d.fecha_sugerida)} <span className="text-xs text-amber-700">(sug.)</span></span> : "—"}</td>
                    <td>{d.hechos}</td>
                    <td className="whitespace-nowrap text-right">
                      <button className="btn-sec mr-1" disabled={!d.paginas && d.estado !== "leido"} onClick={() => verFuente({ documento_id: d.id, pagina: 1 })}>Ver</button>
                      {editor && <button className="btn-sec mr-1" onClick={() => setClasificar(d)}>{d.tipo ? "Clasificación" : "Clasificar"}</button>}
                      {editor && ["error", "requiere_revision", "leido"].includes(d.estado) &&
                        <button className="btn-sec mr-1" title="Las propuestas sin revisar se sustituyen; lo ya revisado se conserva"
                          onClick={() => accion(() => api.post(`/evidencia/documentos/${d.id}/reprocesar`), "Volviendo a leer el documento…")}>Volver a leer</button>}
                      {editor && <button className="btn-peligro" onClick={() => { if (confirm(`¿Eliminar «${d.nombre}» y sus propuestas sin revisar?`)) accion(() => api.borrar(`/evidencia/documentos/${d.id}`), "Documento eliminado."); }}>Eliminar</button>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {clasificar && <Clasificar d={clasificar} tipos={p.catalogos.tipos_documento} onCerrar={() => setClasificar(null)}
        onGuardar={(datos: any) => accion(() => api.patch(`/evidencia/documentos/${clasificar.id}`, datos), "Clasificación guardada.").then((r: any) => { if (r) setClasificar(null); })} />}
    </div>
  );
}

function Clasificar({ d, tipos, onCerrar, onGuardar }: any) {
  const [tipo, setTipo] = useState(d.tipo || d.tipo_sugerido || "");
  const [fechaDoc, setFechaDoc] = useState(d.fecha_documento || d.fecha_sugerida || "");
  return (
    <Modal titulo={`Clasificar «${d.nombre}»`} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onGuardar({ tipo, fecha_documento: fechaDoc || null }); }}>
        {d.tipo_sugerido && !d.tipo && <Aviso tipo="info">Nomira sugiere «{d.tipo_sugerido}»{d.fecha_sugerida && <> con fecha {fecha(d.fecha_sugerida)}</>}. Confírmelo o corríjalo.</Aviso>}
        <label className="block"><span className="etiqueta">Tipo de documento</span>
          <input className="campo" list="tipos-doc" required minLength={2} maxLength={60} value={tipo} onChange={(e) => setTipo(e.target.value)} />
          <datalist id="tipos-doc">{tipos.map((t: string) => <option key={t} value={t} />)}</datalist></label>
        <label className="block"><span className="etiqueta">Fecha del documento (opcional)</span>
          <input className="campo" type="date" value={fechaDoc} onChange={(e) => setFechaDoc(e.target.value)} /></label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Guardar</button></div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ Hechos

function Hechos({ p, id, editor, accion, Fuente }: any) {
  const [filtro, setFiltro] = useState<string>(p.resumen.hechos.por_revisar ? "por_revisar" : "todos");
  const [doc, setDoc] = useState<string>("");
  const [sel, setSel] = useState<number[]>([]);
  const [editar, setEditar] = useState<any>(null);
  const visibles = p.hechos.filter((h: any) => (filtro === "todos" || h.estado === filtro) && (!doc || String(h.documento_id) === doc));
  const filtros: [string, string][] = [["por_revisar", "Por revisar"], ["confirmado", "Confirmados"], ["editado", "Editados"], ["descartado", "Descartados"], ["todos", "Todos"]];
  const cuenta = (k: string) => (k === "todos" ? p.hechos.length : p.resumen.hechos[k]);
  const masivo = (accionM: string) => accion(() => api.post(`/evidencia/asuntos/${id}/hechos/${accionM}`, { ids: sel }),
    accionM === "confirmar" ? `${sel.length} hecho(s) confirmados.` : `${sel.length} hecho(s) descartados.`).then(() => setSel([]));
  return (
    <div className="space-y-4">
      <Aviso tipo="info">Nomira propone hechos a partir de frases del documento que contienen una fecha o un importe. Ninguno cuenta como confirmado hasta que una persona lo revisa. Abra la fuente para comparar con el original.</Aviso>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar hechos">
          {filtros.map(([k, t]) => (
            <button key={k} onClick={() => { setFiltro(k); setSel([]); }} aria-pressed={filtro === k}
              className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${filtro === k ? "bg-marino text-white" : "border border-crema-300 bg-white text-marino hover:bg-marino-50"}`}>
              {t} <span className={filtro === k ? "text-white/70" : "text-slate-400"}>{cuenta(k)}</span></button>
          ))}
          <select className="campo w-auto py-1.5" value={doc} onChange={(e) => setDoc(e.target.value)} aria-label="Filtrar por documento">
            <option value="">Todos los documentos</option>
            {p.documentos.map((d: any) => <option key={d.id} value={d.id}>D{d.id} · {d.nombre}</option>)}
          </select>
        </div>
        {editor && <button className="btn-turquesa" onClick={() => setEditar({ nuevo: true })}>+ Agregar hecho</button>}
      </div>
      {editor && sel.length > 0 && (
        <div className="sticky top-2 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-turquesa bg-turquesa-50 p-3 shadow-suave">
          <span className="text-sm font-semibold text-marino">{sel.length} seleccionado(s)</span>
          <button className="btn-primario" onClick={() => masivo("confirmar")}>Confirmar seleccionados</button>
          <button className="btn-sec" onClick={() => masivo("descartar")}>Descartar seleccionados</button>
          <button className="text-sm text-slate-600 hover:underline" onClick={() => setSel([])}>Quitar selección</button>
        </div>
      )}
      {visibles.length === 0 && <div className="tarjeta p-8 text-center text-sm text-slate-500">{p.hechos.length ? "No hay hechos en este filtro." : "Aún no hay hechos. Suba documentos o agregue uno manualmente."}</div>}
      {editor && filtro === "por_revisar" && visibles.length > 1 && (
        <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={sel.length === visibles.length}
          onChange={(e) => setSel(e.target.checked ? visibles.map((h: any) => h.id) : [])} /> Seleccionar los {visibles.length} visibles</label>
      )}
      <div className="space-y-3">
        {visibles.map((h: any) => (
          <article key={h.id} className={`tarjeta p-4 ${h.estado === "descartado" ? "opacity-70" : ""} ${sel.includes(h.id) ? "border-turquesa" : ""}`}>
            <div className="flex items-start gap-3">
              {editor && h.estado === "por_revisar" && (
                <input type="checkbox" className="mt-1 h-4 w-4 accent-turquesa" checked={sel.includes(h.id)} aria-label="Seleccionar hecho"
                  onChange={(e) => setSel(e.target.checked ? [...sel, h.id] : sel.filter((x) => x !== h.id))} />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Pastilla clase={COLOR_HECHO[h.estado]}>{h.estado_texto}</Pastilla>
                  {h.fecha && <span className="font-marca text-sm font-bold text-marino">{fecha(h.fecha)}</span>}
                  {h.fecha_texto && <span className="text-xs text-slate-500">(«{h.fecha_texto}»)</span>}
                  <span className="text-xs text-slate-400">{h.origen === "manual" ? "Capturado por una persona" : "Propuesto automáticamente"}</span>
                </div>
                <p className={`mt-1.5 text-sm ${h.estado === "descartado" ? "line-through" : "text-slate-800"}`}>{h.descripcion}</p>
                <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                  {h.importe && <span>Importe: <b>{mxn(h.importe)}</b></span>}
                  {h.personas.length > 0 && <span>Personas: {h.personas.join(", ")}</span>}
                  {h.dato && <span>{h.dato}</span>}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                  <Fuente x={h} />
                  <span>{h.confianza == null ? (h.origen === "manual" ? "" : "Lectura: texto del PDF") : `Lectura OCR: ${h.confianza}%`}</span>
                  {h.revisado_por && h.estado !== "por_revisar" && <span>Revisó: {h.revisado_por}, {fechaHora(h.revisado_en)}</span>}
                  {!h.documento_id && <span className="font-semibold text-red-700">No puede confirmarse sin una fuente</span>}
                </div>
              </div>
              {editor && (
                <div className="flex shrink-0 flex-col gap-1.5 sm:flex-row">
                  {h.estado === "por_revisar" && <button className="btn-primario" disabled={!h.documento_id} onClick={() => accion(() => api.post(`/evidencia/hechos/${h.id}/confirmar`), "Hecho confirmado.")}>Confirmar</button>}
                  {h.estado !== "descartado" && <button className="btn-sec" onClick={() => setEditar(h)}>Editar</button>}
                  {h.estado !== "descartado" && <button className="btn-sec" onClick={() => accion(() => api.post(`/evidencia/hechos/${h.id}/descartar`), "Hecho descartado.")}>Descartar</button>}
                  {h.estado !== "por_revisar" && <button className="btn-sec" onClick={() => accion(() => api.post(`/evidencia/hechos/${h.id}/reabrir`), "Hecho devuelto a revisión.")}>Volver a revisión</button>}
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
      {editar && <EditarHecho h={editar.nuevo ? null : editar} documentos={p.documentos} onCerrar={() => setEditar(null)}
        onGuardar={(datos: any) => accion(() => editar.nuevo ? api.post(`/evidencia/asuntos/${id}/hechos`, datos) : api.patch(`/evidencia/hechos/${editar.id}`, datos),
          editar.nuevo ? (datos.documento_id ? "Hecho agregado y confirmado." : "Hecho agregado: queda por revisar hasta asignarle una fuente.") : "Cambios guardados: el hecho queda «Editado por usuario».")
          .then((r: any) => { if (r) setEditar(null); })} />}
    </div>
  );
}

function EditarHecho({ h, documentos, onCerrar, onGuardar }: any) {
  const [f, setF] = useState({
    descripcion: h?.descripcion || "", fecha: h?.fecha || "", personas: (h?.personas || []).join(", "), importe: h?.importe || "",
    dato: h?.dato || "", documento_id: h?.documento_id ? String(h.documento_id) : "", pagina: h?.pagina ? String(h.pagina) : "",
  });
  const cambiar = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const doc = documentos.find((d: any) => String(d.id) === f.documento_id);
  return (
    <Modal titulo={h ? "Editar hecho" : "Agregar hecho"} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        onGuardar({ descripcion: f.descripcion, fecha: f.fecha || null, importe: f.importe || null, dato: f.dato || null,
          personas: f.personas.split(",").map((x: string) => x.trim()).filter(Boolean),
          documento_id: f.documento_id ? Number(f.documento_id) : null, pagina: f.pagina ? Number(f.pagina) : null });
      }}>
        {h?.original && h.origen === "automatico" && <Aviso tipo="info">Propuesta original: «{h.original.descripcion}»{h.original.fecha && ` · ${fecha(h.original.fecha)}`}</Aviso>}
        <label className="block"><span className="etiqueta">Descripción del hecho</span>
          <textarea className="campo" rows={3} required minLength={3} maxLength={2000} value={f.descripcion} onChange={cambiar("descripcion")} /></label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block"><span className="etiqueta">Fecha</span><input className="campo" type="date" value={f.fecha} onChange={cambiar("fecha")} /></label>
          <label className="block"><span className="etiqueta">Importe</span><input className="campo text-right" inputMode="decimal" placeholder="0.00" value={f.importe} onChange={cambiar("importe")} /></label>
          <label className="block"><span className="etiqueta">Otro dato</span><input className="campo" maxLength={300} value={f.dato} onChange={cambiar("dato")} /></label>
        </div>
        <label className="block"><span className="etiqueta">Personas involucradas (separadas por coma)</span><input className="campo" value={f.personas} onChange={cambiar("personas")} /></label>
        <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
          <label className="block"><span className="etiqueta">Documento fuente</span>
            <select className="campo" value={f.documento_id} onChange={cambiar("documento_id")}>
              <option value="">Sin documento (no podrá confirmarse)</option>
              {documentos.map((d: any) => <option key={d.id} value={d.id}>D{d.id} · {d.nombre}</option>)}
            </select></label>
          <label className="block"><span className="etiqueta">Página</span>
            <input className="campo" type="number" min={1} max={doc?.paginas || 10000} value={f.pagina} onChange={cambiar("pagina")} /></label>
        </div>
        <p className="text-xs text-slate-500">{h ? "Al guardar, el hecho queda como «Editado por usuario» (revisado por usted) si conserva su documento fuente."
          : "Con documento fuente, el hecho queda confirmado por usted. Sin fuente, queda por revisar."}</p>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Guardar</button></div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ Cronología

function Cronologia({ p, id, editor, accion, Fuente }: any) {
  const porId = Object.fromEntries(p.hechos.map((h: any) => [h.id, h]));
  const ev = p.cronologia.eventos;
  const porAnio: Record<string, any[]> = {};
  for (const e of ev) (porAnio[e.fecha.slice(0, 4)] ||= []).push(e);
  const revision = (h: any) => h.origen === "manual" ? `Capturado por ${h.creado_por || "usuario"}`
    : h.estado === "editado" ? `Editado por ${h.revisado_por || "usuario"}` : `Confirmado por ${h.revisado_por || "usuario"}`;
  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-500">Solo hechos confirmados o editados por una persona. {p.resumen.hechos.por_revisar > 0 && <>Hay {p.resumen.hechos.por_revisar} propuesta(s) sin revisar que no aparecen aquí.</>}</p>
      {p.contradicciones.length > 0 && (
        <section className="tarjeta border-amber-300">
          <h2 className="border-b border-amber-200 bg-amber-50 px-5 py-3 font-semibold text-amber-900">Posibles contradicciones para revisar ({p.contradicciones.length})</h2>
          <p className="px-5 pt-3 text-xs text-slate-600">Estos hechos describen algo parecido con datos distintos. Nomira no decide cuál es correcto: revise ambas fuentes.</p>
          <div className="divide-y divide-crema-200">
            {p.contradicciones.map((c: any) => (
              <div key={c.par} className="grid gap-3 p-5 md:grid-cols-[1fr_1fr_auto]">
                {c.hechos.map((hid: number, i: number) => {
                  const h = porId[hid];
                  return (
                    <div key={hid} className="rounded-xl bg-crema/60 p-3">
                      <div className="etiqueta">Versión {i ? "B" : "A"} · difiere en {c.difieren.join(" e ")}</div>
                      <div className="font-marca font-bold text-marino">{h.fecha ? fecha(h.fecha) : "Sin fecha"}{h.importe && ` · ${mxn(h.importe)}`}</div>
                      <p className="mt-1 text-sm">{h.descripcion}</p>
                      <div className="mt-1"><Fuente x={h} /></div>
                    </div>
                  );
                })}
                {editor && <button className="btn-sec self-center" title="No cambia los hechos; solo deja de señalar este par"
                  onClick={() => accion(() => api.post(`/evidencia/asuntos/${id}/contradicciones/revisada`, { par: c.par }), "Contradicción marcada como revisada.")}>Marcar como revisada</button>}
              </div>
            ))}
          </div>
        </section>
      )}
      {ev.length === 0 && p.cronologia.sin_fecha.length === 0 && (
        <div className="tarjeta p-10 text-center text-sm text-slate-500">La cronología se forma con los hechos que usted confirme en la pestaña «Hechos».</div>
      )}
      {Object.entries(porAnio).map(([anio, items]) => (
        <section key={anio}>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-slate-400">{anio}</h2>
          <ol className="relative ml-3 space-y-3 border-l-2 border-crema-300 pl-6">
            {items.map((h: any) => (
              <li key={h.id} className="relative">
                <span className={`absolute -left-[33px] top-4 h-4 w-4 rounded-full border-4 border-crema ${h.contradicciones.length ? "bg-amber-500" : "bg-turquesa"}`} aria-hidden />
                <div className={`tarjeta p-4 ${h.contradicciones.length ? "border-amber-300" : ""}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-marca font-extrabold text-marino">{fecha(h.fecha)}</span>
                    {h.contradicciones.length > 0 && <Pastilla clase="bg-amber-100 text-amber-800">Posible contradicción para revisar</Pastilla>}
                  </div>
                  <p className="mt-1 text-sm text-slate-800">{h.descripcion}</p>
                  <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    <Fuente x={h} />
                    {h.importe && <span>Importe: {mxn(h.importe)}</span>}
                    {h.personas.length > 0 && <span>{h.personas.join(", ")}</span>}
                    <span>{revision(h)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}
      {p.cronologia.sin_fecha.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-slate-400">Hechos revisados sin fecha</h2>
          <div className="space-y-2">
            {p.cronologia.sin_fecha.map((h: any) => (
              <div key={h.id} className="tarjeta p-4 text-sm"><p>{h.descripcion}</p>
                <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-slate-500"><Fuente x={h} />{h.importe && <span>Importe: {mxn(h.importe)}</span>}<span>{revision(h)}</span></div></div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Matriz

function Matriz({ p, id, editor, accion, Fuente }: any) {
  const [nuevo, setNuevo] = useState("");
  const [vincular, setVincular] = useState<any>(null);
  const revisados = p.hechos.filter((h: any) => ["confirmado", "editado"].includes(h.estado) && h.documento_id);
  return (
    <div className="space-y-4">
      <Aviso tipo="info">Agregue los hechos que necesita acreditar y vincule la evidencia. El estado de cada punto lo decide usted; Nomira solo sugiere y no evalúa relevancia ni suficiencia jurídica.</Aviso>
      {editor && (
        <form className="tarjeta flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); accion(() => api.post(`/evidencia/asuntos/${id}/puntos`, { descripcion: nuevo }), "Punto agregado.").then((r: any) => { if (r) setNuevo(""); }); }}>
          <label className="block grow"><span className="etiqueta">Hecho que se busca acreditar</span>
            <input className="campo" required minLength={3} maxLength={2000} value={nuevo} onChange={(e) => setNuevo(e.target.value)} placeholder="p. ej. Fecha de inicio de la relación de trabajo" /></label>
          <button className="btn-turquesa">Agregar a la matriz</button>
        </form>
      )}
      {p.puntos.length === 0 && <div className="tarjeta p-10 text-center text-sm text-slate-500">La matriz está vacía.</div>}
      {p.puntos.map((pt: any) => (
        <section key={pt.id} className="tarjeta p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h3 className="font-marca text-lg font-bold text-marino">{pt.descripcion}</h3>
              {pt.estado_decidido_por ? <p className="text-xs text-slate-500">Estado decidido por {pt.estado_decidido_por}, {fechaHora(pt.estado_decidido_en)}</p>
                : <p className="text-xs text-slate-500">Sin decisión registrada</p>}
            </div>
            <div className="flex items-center gap-2">
              {editor ? (
                <select className={`campo w-auto font-semibold ${COLOR_PUNTO[pt.estado]}`} value={pt.estado} aria-label="Estado del punto"
                  onChange={(e) => accion(() => api.patch(`/evidencia/puntos/${pt.id}`, { estado: e.target.value }), "Estado actualizado.")}>
                  {Object.entries(p.catalogos.estados_punto).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
                </select>
              ) : <Pastilla clase={COLOR_PUNTO[pt.estado]}>{pt.estado_texto}</Pastilla>}
              {editor && <button className="btn-peligro" aria-label="Quitar punto" onClick={() => { if (confirm("¿Quitar este punto de la matriz?")) accion(() => api.borrar(`/evidencia/puntos/${pt.id}`), "Punto eliminado."); }}>✕</button>}
            </div>
          </div>
          {pt.sugerencia.estado !== pt.estado && (
            <p className="mt-2 rounded-lg bg-crema/70 px-3 py-2 text-xs text-slate-600">
              <b>Sugerencia del sistema (por revisar):</b> {p.catalogos.estados_punto[pt.sugerencia.estado]}. {pt.sugerencia.motivo}
              {editor && <button className="ml-2 font-semibold text-turquesa-700 hover:underline" onClick={() => accion(() => api.patch(`/evidencia/puntos/${pt.id}`, { estado: pt.sugerencia.estado }), "Estado actualizado.")}>Usar</button>}
            </p>
          )}
          <ul className="mt-3 space-y-2">
            {pt.vinculos.length === 0 && <li className="text-sm text-slate-500">Sin evidencia vinculada.</li>}
            {pt.vinculos.map((v: any) => (
              <li key={v.id} className="flex items-start justify-between gap-3 rounded-xl border border-crema-300 p-3 text-sm">
                <div className="min-w-0">
                  {v.hecho ? <p>{v.hecho.fecha && <b className="text-marino">{fecha(v.hecho.fecha)} · </b>}{v.hecho.descripcion}</p> : <p className="text-slate-600">Documento completo o página</p>}
                  <div className="mt-1 flex flex-wrap gap-x-3 text-xs"><Fuente x={v.hecho || v} />{v.nota && <span className="text-slate-500">{v.nota}</span>}</div>
                </div>
                {editor && <button className="shrink-0 text-xs text-red-700 hover:underline" onClick={() => accion(() => api.borrar(`/evidencia/vinculos/${v.id}`), "Vínculo quitado.")}>Quitar</button>}
              </li>
            ))}
          </ul>
          {editor && <button className="mt-3 text-sm font-semibold text-turquesa-700 hover:underline" onClick={() => setVincular(pt)}>+ Vincular evidencia</button>}
        </section>
      ))}
      {vincular && <Vincular punto={vincular} hechos={revisados} documentos={p.documentos} onCerrar={() => setVincular(null)}
        onGuardar={(datos: any) => accion(() => api.post(`/evidencia/puntos/${vincular.id}/vinculos`, datos), "Evidencia vinculada.").then((r: any) => { if (r) setVincular(null); })} />}
    </div>
  );
}

function Vincular({ punto, hechos, documentos, onCerrar, onGuardar }: any) {
  const [modo, setModo] = useState<"hecho" | "documento">(hechos.length ? "hecho" : "documento");
  const [hecho, setHecho] = useState("");
  const [doc, setDoc] = useState("");
  const [pagina, setPagina] = useState("");
  const [nota, setNota] = useState("");
  const [buscar, setBuscar] = useState("");
  const lista = hechos.filter((h: any) => !buscar || h.descripcion.toLowerCase().includes(buscar.toLowerCase()));
  return (
    <Modal titulo={`Vincular evidencia: ${punto.descripcion}`} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        onGuardar(modo === "hecho" ? { hecho_id: Number(hecho), nota: nota || null } : { documento_id: Number(doc), pagina: pagina ? Number(pagina) : null, nota: nota || null });
      }}>
        <div className="flex gap-2">
          <button type="button" className={modo === "hecho" ? "btn-primario" : "btn-sec"} onClick={() => setModo("hecho")}>Un hecho confirmado</button>
          <button type="button" className={modo === "documento" ? "btn-primario" : "btn-sec"} onClick={() => setModo("documento")}>Un documento o página</button>
        </div>
        {modo === "hecho" ? (
          hechos.length === 0 ? <Aviso tipo="alerta">Aún no hay hechos confirmados. Confírmelos en la pestaña «Hechos».</Aviso> : (
            <>
              <input className="campo" placeholder="Buscar hecho" value={buscar} onChange={(e) => setBuscar(e.target.value)} />
              <div className="max-h-72 space-y-1.5 overflow-auto">
                {lista.map((h: any) => (
                  <label key={h.id} className={`flex cursor-pointer gap-2 rounded-xl border p-2.5 text-sm ${hecho === String(h.id) ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
                    <input type="radio" name="hecho" value={h.id} checked={hecho === String(h.id)} onChange={(e) => setHecho(e.target.value)} required />
                    <span>{h.fecha && <b className="text-marino">{fecha(h.fecha)} · </b>}{h.descripcion}</span>
                  </label>
                ))}
              </div>
            </>
          )
        ) : (
          <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
            <label className="block"><span className="etiqueta">Documento</span>
              <select className="campo" required value={doc} onChange={(e) => setDoc(e.target.value)}>
                <option value="">Seleccione…</option>
                {documentos.map((d: any) => <option key={d.id} value={d.id}>D{d.id} · {d.nombre}</option>)}
              </select></label>
            <label className="block"><span className="etiqueta">Página</span><input className="campo" type="number" min={1} value={pagina} onChange={(e) => setPagina(e.target.value)} /></label>
          </div>
        )}
        <label className="block"><span className="etiqueta">Nota (opcional)</span><input className="campo" maxLength={500} value={nota} onChange={(e) => setNota(e.target.value)} /></label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={modo === "hecho" && !hechos.length}>Vincular</button></div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ Pendientes

function Pendientes({ p, id, editor, accion, setError }: any) {
  const vacio = { descripcion: "", responsable: "", fecha_seguimiento: "", nota: "" };
  const [f, setF] = useState(vacio);
  const [editar, setEditar] = useState<any>(null);
  const exportar = (formato: string) => api.descargar(`/evidencia/asuntos/${id}/exportar/${formato}?solo=pendientes`, `pendientes-${id}.${formato === "pdf" ? "pdf" : "xlsx"}`).catch((e: any) => setError(e.message));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Documentos o datos que faltan. La lista para el cliente incluye solo lo abierto y no muestra notas internas. Nomira no envía mensajes.</p>
        <div className="flex gap-2"><button className="btn-sec" onClick={() => exportar("pdf")}>Lista para el cliente (PDF)</button><button className="btn-sec" onClick={() => exportar("excel")}>Excel</button></div>
      </div>
      {editor && (
        <form className="tarjeta grid gap-3 p-4 md:grid-cols-[2fr_1fr_10rem_auto]" onSubmit={(e) => {
          e.preventDefault();
          accion(() => api.post(`/evidencia/asuntos/${id}/pendientes`, { ...f, fecha_seguimiento: f.fecha_seguimiento || null, responsable: f.responsable || null, nota: f.nota || null }), "Pendiente agregado.").then((r: any) => { if (r) setF(vacio); });
        }}>
          <label className="block"><span className="etiqueta">Documento o dato pendiente</span><input className="campo" required minLength={3} maxLength={2000} value={f.descripcion} onChange={(e) => setF({ ...f, descripcion: e.target.value })} /></label>
          <label className="block"><span className="etiqueta">Responsable</span><input className="campo" maxLength={200} placeholder="Cliente, abogado…" value={f.responsable} onChange={(e) => setF({ ...f, responsable: e.target.value })} /></label>
          <label className="block"><span className="etiqueta">Seguimiento</span><input className="campo" type="date" value={f.fecha_seguimiento} onChange={(e) => setF({ ...f, fecha_seguimiento: e.target.value })} /></label>
          <button className="btn-turquesa self-end">Agregar</button>
        </form>
      )}
      {p.pendientes.length === 0 ? <div className="tarjeta p-10 text-center text-sm text-slate-500">Sin pendientes.</div> : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Pendiente</th><th>Responsable</th><th>Seguimiento</th><th>Estado</th><th>Nota interna</th><th></th></tr></thead>
            <tbody>
              {p.pendientes.map((x: any) => (
                <tr key={x.id} className={["recibido", "cancelado"].includes(x.estado) ? "text-slate-400" : ""}>
                  <td className="font-semibold">{x.descripcion}</td>
                  <td>{x.responsable || "—"}</td>
                  <td className={`whitespace-nowrap ${x.vencido ? "font-semibold text-red-700" : ""}`}>{fecha(x.fecha_seguimiento)}{x.vencido && " · vencido"}</td>
                  <td>{editor ? (
                    <select className="campo w-auto py-1" value={x.estado} aria-label="Estado del pendiente"
                      onChange={(e) => accion(() => api.patch(`/evidencia/pendientes/${x.id}`, { estado: e.target.value }))}>
                      {Object.entries(p.catalogos.estados_pendiente).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
                    </select>) : x.estado_texto}</td>
                  <td className="max-w-xs text-xs text-slate-600">{x.nota || "—"}</td>
                  <td className="whitespace-nowrap text-right">
                    {editor && <button className="btn-sec mr-1" onClick={() => setEditar(x)}>Editar</button>}
                    {editor && <button className="btn-peligro" aria-label="Eliminar pendiente" onClick={() => { if (confirm("¿Eliminar este pendiente?")) accion(() => api.borrar(`/evidencia/pendientes/${x.id}`), "Pendiente eliminado."); }}>✕</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editar && <EditarPendiente x={editar} onCerrar={() => setEditar(null)}
        onGuardar={(datos: any) => accion(() => api.patch(`/evidencia/pendientes/${editar.id}`, datos), "Pendiente actualizado.").then((r: any) => { if (r) setEditar(null); })} />}
    </div>
  );
}

function EditarPendiente({ x, onCerrar, onGuardar }: any) {
  const [f, setF] = useState({ descripcion: x.descripcion, responsable: x.responsable || "", fecha_seguimiento: x.fecha_seguimiento || "", nota: x.nota || "" });
  return (
    <Modal titulo="Editar pendiente" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onGuardar({ ...f, responsable: f.responsable || null, fecha_seguimiento: f.fecha_seguimiento || null, nota: f.nota || null }); }}>
        <label className="block"><span className="etiqueta">Pendiente</span><input className="campo" required minLength={3} value={f.descripcion} onChange={(e) => setF({ ...f, descripcion: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Responsable</span><input className="campo" value={f.responsable} onChange={(e) => setF({ ...f, responsable: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Fecha de seguimiento</span><input className="campo" type="date" value={f.fecha_seguimiento} onChange={(e) => setF({ ...f, fecha_seguimiento: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Nota interna (no sale en la lista para el cliente)</span><textarea className="campo" rows={2} value={f.nota} onChange={(e) => setF({ ...f, nota: e.target.value })} /></label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Guardar</button></div>
      </form>
    </Modal>
  );
}
