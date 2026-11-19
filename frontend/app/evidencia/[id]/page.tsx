"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FormAsunto } from "@/components/EvFormAsunto";
import EvVisor from "@/components/EvVisor";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha, fechaHora, mxn } from "@/lib/api";

const LECTURA: Record<string, [string, string]> = {
  recibido: ["Recibido — pendiente de revisión", "bg-violet-100 text-violet-800"],
  pendiente: ["En cola", "bg-blue-100 text-blue-800"], procesando: ["Leyendo…", "bg-blue-100 text-blue-800"],
  leido: ["Leído", "bg-emerald-100 text-emerald-800"], requiere_revision: ["Requiere revisión", "bg-amber-100 text-amber-800"],
  error: ["No legible", "bg-red-100 text-red-800"],
};
const COLOR_HECHO: Record<string, string> = {
  por_revisar: "bg-amber-100 text-amber-800", confirmado: "bg-emerald-100 text-emerald-800",
  editado: "bg-turquesa-100 text-turquesa-700", descartado: "bg-slate-200 text-slate-600",
};
const COLOR_TIPO: Record<string, string> = {
  fecha_evento: "bg-turquesa-50 text-turquesa-700", fecha_documento: "bg-slate-100 text-slate-700", importe: "bg-sky-50 text-sky-800",
  persona: "bg-violet-50 text-violet-800", lugar: "bg-orange-50 text-orange-800", administrativo: "bg-slate-100 text-slate-600",
  otro: "bg-slate-100 text-slate-600",
};
const COLOR_SOLICITUD: Record<string, string> = {
  activa: "bg-emerald-100 text-emerald-800", vencida: "bg-slate-200 text-slate-600", revocada: "bg-red-100 text-red-800",
  completa: "bg-sky-100 text-sky-800",
};
const COLOR_PUNTO: Record<string, string> = {
  pendiente_evidencia: "bg-slate-100 text-slate-700", respaldado: "bg-emerald-100 text-emerald-800",
  parcial: "bg-sky-100 text-sky-800", contradictorio: "bg-amber-100 text-amber-800",
};

function Pastilla({ clase, children }: { clase: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${clase}`}>{children}</span>;
}

type Pestana = "atencion" | "documentos" | "hechos" | "diferencias" | "cronologia" | "matriz" | "pendientes" | "buscar" | "historial";

export default function Asunto() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const sesion = useSesion();
  const editor = !!sesion && sesion.usuario.rol !== "consulta";
  const [p, setP] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [pestana, setPestana] = useState<Pestana>("atencion");
  const [visor, setVisor] = useState<any>(null);
  const [editarAsunto, setEditarAsunto] = useState(false);
  const [eliminar, setEliminar] = useState(false);
  const [editarHecho, setEditarHecho] = useState<any>(null);
  const [historialHecho, setHistorialHecho] = useState<any>(null);
  const [vincularHecho, setVincularHecho] = useState<any>(null);

  const cargar = useCallback(async () => {
    try { setP(await api.get(`/evidencia/asuntos/${id}`)); } catch (e: any) { setError(e.message); }
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
    try { const r = await fn(); if (mensaje) setOk(mensaje); await cargar(); return r ?? true; } catch (e: any) { setError(e.message); }
  }
  const docs = useMemo(() => Object.fromEntries((p?.documentos || []).map((d: any) => [d.id, d])), [p]);
  const verFuente = (x: any) => {
    const d = docs[x.documento_id];
    if (d) setVisor({ documento: d, pagina: x.pagina, bbox: x.bbox, fragmento: x.fragmento });
  };
  const Fuente = ({ x }: { x: any }) => {
    const d = docs[x.documento_id];
    if (!d) return <span className="text-xs font-semibold text-red-700">{x.documento_id ? "Fuente restringida" : "Sin documento fuente"}</span>;
    return (
      <button className="text-left text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => verFuente(x)} title="Abrir el documento en la página de origen">
        D{d.id} · {d.nombre}{x.pagina ? `, p. ${x.pagina}` : ""} ↗
      </button>
    );
  };
  // Lo que comparten las pestañas para revisar hechos sin cambiar de pantalla
  const ctx = { p, id, editor, accion, Fuente, verFuente, setError, ir: setPestana,
    editar: (h: any) => setEditarHecho(h), historial: (h: any) => setHistorialHecho(h), vincular: (h: any) => setVincularHecho(h) };

  if (!p) return <Shell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</Shell>;
  const a = p.asunto, r = p.resumen;
  const atencion = r.documentos_recibidos + r.diferencias_pendientes + r.hechos.por_revisar + r.pendientes_vencidos + r.pendientes_proximos
    + r.documentos_sin_clasificar + r.puntos_sin_vinculos + r.documentos_por_revisar;
  const tabs: [Pestana, string, number?, boolean?][] = [
    ["atencion", "Requiere tu atención", atencion, true], ["documentos", "Documentos", r.documentos], ["hechos", "Hechos", r.hechos.por_revisar, true],
    ["diferencias", "Diferencias", r.diferencias_pendientes, true], ["cronologia", "Cronología"],
    ["matriz", "Matriz", p.puntos.length], ["pendientes", "Pendientes", r.pendientes_abiertos], ["buscar", "Buscar"], ["historial", "Historial"],
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
            {[a.cliente && `Cliente: ${a.cliente}`, a.jurisdiccion_texto, a.identificador_interno && `Ref. interna ${a.identificador_interno}`,
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
      <p className="mt-3 text-xs text-slate-500">Nomira ayuda a localizar, comparar y organizar la información de los documentos. No decide si un hecho es verdadero, relevante, admisible ni jurídicamente suficiente.</p>

      <div className="mt-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {enProceso && <div className="mt-2"><Aviso tipo="info">Leyendo {r.documentos_en_proceso} documento(s)… esta página se actualiza sola.</Aviso></div>}
      {r.documentos_restringidos_ocultos > 0 && <div className="mt-2"><Aviso tipo="info">{r.documentos_restringidos_ocultos} documento(s) restringido(s) de este asunto no son visibles para su usuario.</Aviso></div>}

      <div className="mb-5 mt-4 flex gap-1 overflow-x-auto border-b border-crema-300" role="tablist">
        {tabs.map(([k, t, n, alerta]) => (
          <button key={k} role="tab" aria-selected={pestana === k} onClick={() => setPestana(k)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${pestana === k ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>
            {t}{n ? <span className={`ml-1.5 rounded-full px-1.5 text-[11px] ${alerta ? "bg-amber-100 text-amber-800" : "bg-crema-200 text-slate-600"}`}>{n}</span> : null}
          </button>
        ))}
      </div>

      {pestana === "atencion" && <Atencion {...ctx} />}
      {pestana === "documentos" && <Documentos {...ctx} />}
      {pestana === "hechos" && <Hechos {...ctx} />}
      {pestana === "diferencias" && <Diferencias {...ctx} />}
      {pestana === "cronologia" && <Cronologia {...ctx} />}
      {pestana === "matriz" && <Matriz {...ctx} />}
      {pestana === "pendientes" && <Pendientes {...ctx} />}
      {pestana === "buscar" && <Buscar {...ctx} />}
      {pestana === "historial" && <HistorialAsunto {...ctx} />}

      {visor && <EvVisor {...visor} onCerrar={() => setVisor(null)} />}
      {editarHecho && <EditarHecho h={editarHecho.nuevo ? null : editarHecho} documentos={p.documentos} tipos={p.catalogos.tipos_dato} onCerrar={() => setEditarHecho(null)}
        onGuardar={(datos: any) => accion(() => editarHecho.nuevo ? api.post(`/evidencia/asuntos/${id}/hechos`, datos) : api.patch(`/evidencia/hechos/${editarHecho.id}`, datos),
          editarHecho.nuevo ? (datos.documento_id ? "Hecho agregado y confirmado por usted." : "Hecho agregado: queda propuesto hasta asignarle una fuente.") : "Cambios guardados: queda «Editado por una persona».")
          .then((x: any) => { if (x) setEditarHecho(null); })} />}
      {historialHecho && <Historial h={historialHecho} onCerrar={() => setHistorialHecho(null)} />}
      {vincularHecho && <VincularHecho h={vincularHecho} p={p} id={id} onCerrar={() => setVincularHecho(null)} accion={accion} />}
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
  const [modo, setModo] = useState<"yo" | "cliente">("yo");
  const [pedir, setPedir] = useState(false);
  const [creada, setCreada] = useState<any>(null);
  const [comparar, setComparar] = useState<[number, number] | null>(null);
  const r = p.resumen;
  async function subir(lista: FileList | null) {
    if (!lista?.length) return;
    const fd = new FormData();
    Array.from(lista).forEach((f) => fd.append("archivos", f));
    setSubiendo(true);
    const res = await accion(() => api.subir(`/evidencia/asuntos/${id}/documentos`, fd));
    if (res) setSubida(res);
    setSubiendo(false);
    if (entrada.current) entrada.current.value = "";
  }
  const recibidos = p.documentos.filter((d: any) => d.estado === "recibido");
  return (
    <div className="space-y-4">
      {editor && (
        <section className="tarjeta overflow-hidden">
          <div className="grid sm:grid-cols-2" role="tablist" aria-label="Cómo agregar documentos">
            {([["yo", "Subirlos yo", "Usted carga los archivos desde su equipo."], ["cliente", "Pedírselos al cliente", "Le enviamos un enlace seguro por correo para que él los suba."]] as const).map(([k, t, d]) => (
              <button key={k} role="tab" aria-selected={modo === k} onClick={() => setModo(k)}
                className={`border-b-2 px-5 py-3.5 text-left transition ${modo === k ? "border-turquesa bg-turquesa-50/60" : "border-transparent hover:bg-crema/60"}`}>
                <span className="block font-semibold text-marino">{t}</span><span className="block text-xs text-slate-500">{d}</span>
              </button>
            ))}
          </div>
          {modo === "yo" ? (
            <div className="m-4 flex flex-wrap items-center gap-3 rounded-xl border-2 border-dashed border-crema-300 p-5" onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); subir(e.dataTransfer.files); }}>
              <input ref={entrada} type="file" multiple className="hidden" accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" onChange={(e) => subir(e.target.files)} />
              <button className="btn-turquesa" disabled={subiendo} onClick={() => entrada.current?.click()}>{subiendo ? "Subiendo…" : "Subir documentos"}</button>
              <span className="text-sm text-slate-500">PDF o imágenes (JPG, PNG, WebP), o arrástrelos aquí. El original se guarda sin cambios; Nomira lo lee y propone su tipo, fecha y datos.</span>
            </div>
          ) : (
            <div className="m-4 flex flex-wrap items-center gap-3 rounded-xl border border-crema-300 bg-crema/40 p-5">
              <button className="btn-turquesa" onClick={() => setPedir(true)}>Solicitar documentos</button>
              <span className="max-w-2xl text-sm text-slate-600">El cliente recibe un correo con un enlace que <b>solo sirve para subir archivos</b> a este asunto (no ve nada del expediente). Lo que envíe llega como «Recibido — pendiente de revisión» y Nomira no lo lee hasta que usted lo acepte.</span>
            </div>
          )}
        </section>
      )}
      {recibidos.length > 0 && (
        <Aviso tipo="alerta"><b>{recibidos.length} documento(s) enviados por el cliente esperan su revisión.</b> Revíselos con «Ver» y elija «Aceptar y leer» o «Rechazar». No se leen ni se analizan hasta que usted los acepte.</Aviso>
      )}
      {subida && <div className="space-y-1">{subida.map((s, i) => <Aviso key={i} tipo={s.aceptado ? "ok" : "alerta"}><b>{s.nombre}:</b> {s.aceptado ? "recibido; leyendo." : s.motivo}</Aviso>)}</div>}
      {p.documentos.length === 0 ? (
        <div className="tarjeta p-10 text-center text-sm text-slate-500">Aún no hay documentos en este asunto.</div>
      ) : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Ref.</th><th>Documento</th><th>Lectura</th><th>Tipo</th><th>Fecha del documento</th><th>Datos</th><th>Visibilidad</th><th></th></tr></thead>
            <tbody>
              {p.documentos.map((d: any) => {
                const [txt, clase] = LECTURA[d.estado];
                const delCliente = d.origen === "cliente";
                return (
                  <tr key={d.id} className={d.estado === "recibido" ? "bg-violet-50/40" : ""}>
                    <td className="font-mono text-xs font-semibold">D{d.id}</td>
                    <td><div className="font-semibold">{d.nombre}</div>
                      <div className="text-xs text-slate-500">{d.formato.toUpperCase()} · {d.paginas ?? "?"} pág. · {(d.tamano_bytes / 1048576).toFixed(1)} MB · {delCliente ? "Enviado por el cliente" : d.subido_por || "—"}, {fechaHora(d.creado_en)}</div>
                      {delCliente && d.solicitado_como && <div className="text-xs text-slate-500">Enviado como «{d.solicitado_como}»</div>}
                      {delCliente && d.aceptado_por && <div className="text-xs text-slate-500">Aceptado por {d.aceptado_por}, {fechaHora(d.aceptado_en)}</div>}
                      {d.error && <div className="mt-1 max-w-md text-xs text-amber-800">{d.error}</div>}
                      {d.resumen_lectura?.relectura && <div className="mt-1 text-xs text-slate-500">Última lectura ({fechaHora(d.resumen_lectura.fecha)}): {d.resumen_lectura.nuevas} propuesta(s) nueva(s); {d.resumen_lectura.conservadas} revisada(s) por personas se conservaron{d.resumen_lectura.ya_revisadas ? ` y ${d.resumen_lectura.ya_revisadas} equivalente(s) no se repitieron` : ""}.</div>}
                      {d.relacionados?.map((x: any) => (
                        <div key={x.id} className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
                          <Pastilla clase="bg-sky-50 text-sky-800">{x.tipo === "duplicado" ? "Posible duplicado" : "Posible versión"} de D{x.id}</Pastilla>
                          <span className="text-slate-500">{x.es_mas_reciente ? `«${x.nombre}» se cargó después` : "este se cargó después"} (no indica cuál es la vigente)</span>
                          <button className="font-semibold text-turquesa-700 hover:underline" onClick={() => setComparar([d.id, x.id])}>Comparar</button>
                        </div>))}</td>
                    <td><Pastilla clase={clase}>{txt}</Pastilla></td>
                    <td>{d.tipo ? <span className="font-semibold">{d.tipo}</span>
                      : d.tipo_sugerido ? <span className="text-slate-600">{d.tipo_sugerido} <span className="text-xs text-amber-700">(sugerido)</span></span>
                        : <span className="text-slate-400">Sin clasificar</span>}</td>
                    <td className="whitespace-nowrap">{d.fecha_documento ? fecha(d.fecha_documento)
                      : d.fecha_sugerida ? <span className="text-slate-600">{fecha(d.fecha_sugerida)} <span className="text-xs text-amber-700">(sug.)</span></span> : "—"}</td>
                    <td>{d.estado === "recibido" ? "—" : d.hechos}</td>
                    <td>{editor ? (
                      <select className="campo w-auto py-1 text-xs" value={d.visibilidad} aria-label={`Visibilidad de ${d.nombre}`}
                        title="Restringido: solo administradores, el responsable del asunto y quien lo cargó"
                        onChange={(e) => accion(() => api.patch(`/evidencia/documentos/${d.id}/visibilidad`, { visibilidad: e.target.value }), "Visibilidad actualizada.")}>
                        {Object.entries(p.catalogos.visibilidad).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
                      </select>) : <span className="text-xs">{d.visibilidad_texto}</span>}</td>
                    <td className="whitespace-nowrap text-right">
                      <button className="btn-sec mr-1" disabled={d.estado === "recibido" ? false : !d.paginas && d.estado !== "leido"} onClick={() => verFuente({ documento_id: d.id, pagina: 1 })}>Ver</button>
                      {editor && d.estado === "recibido" && <>
                        <button className="btn-primario mr-1" onClick={() => accion(() => api.post(`/evidencia/documentos/${d.id}/aceptar`), `«${d.nombre}» aceptado: Nomira lo está leyendo.`)}>Aceptar y leer</button>
                        <button className="btn-peligro" onClick={() => { if (confirm(`¿Rechazar «${d.nombre}»? Se borrará del asunto.`)) accion(() => api.borrar(`/evidencia/documentos/${d.id}`), "Documento rechazado y borrado."); }}>Rechazar</button>
                      </>}
                      {editor && d.estado !== "recibido" && <button className="btn-sec mr-1" onClick={() => setClasificar(d)}>{d.tipo ? "Clasificación" : "Clasificar"}</button>}
                      {editor && ["error", "requiere_revision", "leido"].includes(d.estado) &&
                        <button className="btn-sec mr-1" title="Las propuestas sin revisar se sustituyen; lo ya revisado se conserva"
                          onClick={() => accion(() => api.post(`/evidencia/documentos/${d.id}/reprocesar`), "Volviendo a leer el documento…")}>Volver a leer</button>}
                      {editor && d.estado !== "recibido" && <button className="btn-peligro" onClick={() => { if (confirm(`¿Eliminar «${d.nombre}» y sus propuestas sin revisar?`)) accion(() => api.borrar(`/evidencia/documentos/${d.id}`), "Documento eliminado."); }}>Eliminar</button>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {p.solicitudes.length > 0 && <Solicitudes p={p} editor={editor} accion={accion} />}
      {clasificar && <Clasificar d={clasificar} tipos={p.catalogos.tipos_documento} onCerrar={() => setClasificar(null)}
        onGuardar={(datos: any) => accion(() => api.patch(`/evidencia/documentos/${clasificar.id}`, datos), "Clasificación guardada.").then((x: any) => { if (x) setClasificar(null); })} />}
      {pedir && <PedirDocumentos p={p} id={id} onCerrar={() => setPedir(false)}
        onCreada={(x: any) => { setPedir(false); setCreada(x); accion(async () => null); }} />}
      {creada && <SolicitudCreada r={creada} onCerrar={() => setCreada(null)} />}
      {comparar && <Comparar a={comparar[0]} b={comparar[1]} onCerrar={() => setComparar(null)} />}
    </div>
  );
}

function Comparar({ a, b, onCerrar }: any) {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [soloCambios, setSoloCambios] = useState(true);
  useEffect(() => { api.get(`/evidencia/documentos/${a}/comparar/${b}`).then(setR).catch((e) => setError(e.message)); }, [a, b]);
  return (
    <Modal titulo="Comparar documentos" onCerrar={onCerrar} ancho="max-w-4xl">
      <Aviso>{error}</Aviso>
      {!r && !error && <p className="text-sm text-slate-500">Comparando…</p>}
      {r && (
        <div className="space-y-3 text-sm">
          <div className="grid gap-2 sm:grid-cols-2">
            {[r.a, r.b].map((d: any, i: number) => (
              <div key={d.id} className={`rounded-xl p-3 ${i ? "bg-emerald-50" : "bg-red-50"}`}>
                <div className="etiqueta">{i ? "B" : "A"} · D{d.id}</div><b>{d.nombre}</b>
                <div className="text-xs text-slate-500">Cargado {fechaHora(d.creado_en)}{d.id === r.mas_reciente_id && " · el más reciente en cargarse"}</div>
              </div>))}
          </div>
          <p className="text-xs text-slate-500">Se compara el texto leído (puede tener errores de OCR). Ambos originales se conservan; «más reciente» se refiere a la carga, no a cuál es la versión vigente.</p>
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={soloCambios} onChange={(e) => setSoloCambios(e.target.checked)} /> Mostrar solo las diferencias ({r.cambios})</label>
          <div className="max-h-[55vh] overflow-auto rounded-xl border border-crema-300 font-mono text-xs">
            {r.lineas.filter((x: any) => !soloCambios || x.tipo !== "igual").map((x: any, i: number) => (
              <div key={i} className={`px-3 py-0.5 ${x.tipo === "solo_a" ? "bg-red-50 text-red-900" : x.tipo === "solo_b" ? "bg-emerald-50 text-emerald-900" : "text-slate-600"}`}>
                {x.tipo === "solo_a" ? "A − " : x.tipo === "solo_b" ? "B + " : "    "}{x.texto}</div>))}
            {r.cambios === 0 && <p className="p-3 text-slate-500">El texto leído es idéntico.</p>}
          </div>
        </div>
      )}
    </Modal>
  );
}

function Solicitudes({ p, editor, accion }: any) {
  return (
    <section className="tarjeta overflow-x-auto">
      <div className="border-b border-crema-300 px-5 py-3"><h2 className="font-semibold text-marino">Solicitudes enviadas al cliente</h2>
        <p className="text-xs text-slate-500">Cada enlace solo permite subir archivos a este asunto. Puede revocarlo en cualquier momento.</p></div>
      <table className="tabla">
        <thead><tr><th>Para</th><th>Estado</th><th>Vence</th><th>Archivos</th><th>Último uso</th><th>Creada por</th><th></th></tr></thead>
        <tbody>
          {p.solicitudes.map((s: any) => (
            <tr key={s.id}>
              <td><div className="font-semibold">{s.email}</div>
                {s.documentos.length > 0 && <div className="max-w-xs truncate text-xs text-slate-500" title={s.documentos.join(", ")}>{s.documentos.join(", ")}</div>}
                <div className="text-[11px] text-slate-400">Enlace …{s.pista} · {s.requiere_codigo ? "con código por correo" : "sin código"}</div></td>
              <td><Pastilla clase={COLOR_SOLICITUD[s.estado]}>{s.estado_texto}</Pastilla>
                {s.revocada_por && <div className="mt-1 text-[11px] text-slate-500">por {s.revocada_por}</div>}</td>
              <td className="whitespace-nowrap">{fechaHora(s.expira_en)}</td>
              <td>{s.archivos_recibidos} de {s.max_archivos}</td>
              <td className="whitespace-nowrap text-xs">{s.ultima_carga_en ? `Subió el ${fechaHora(s.ultima_carga_en)}` : s.ultimo_acceso_en ? `Abrió el ${fechaHora(s.ultimo_acceso_en)}` : <span className="text-slate-400">Sin abrir</span>}</td>
              <td className="text-xs">{s.creado_por || "—"}<div className="text-slate-400">{fechaHora(s.creado_en)}</div></td>
              <td className="text-right">{editor && s.estado === "activa" &&
                <button className="btn-peligro" onClick={() => { if (confirm(`¿Revocar el enlace enviado a ${s.email}? Dejará de funcionar de inmediato.`)) accion(() => api.post(`/evidencia/solicitudes/${s.id}/revocar`), "Enlace revocado."); }}>Revocar</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function PedirDocumentos({ p, id, onCerrar, onCreada }: any) {
  const abiertos = p.pendientes.filter((x: any) => ["pendiente", "solicitado"].includes(x.estado));
  const [f, setF] = useState({ email: "", mensaje: "", dias: 7, requiere_codigo: true });
  const [lista, setLista] = useState<string[]>(abiertos.filter((x: any) => /client/i.test(x.responsable || "")).map((x: any) => x.descripcion));
  const [otro, setOtro] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const alternar = (t: string) => setLista(lista.includes(t) ? lista.filter((x) => x !== t) : [...lista, t]);
  const agregar = () => { const t = otro.trim(); if (t && !lista.includes(t)) setLista([...lista, t]); setOtro(""); };
  const extras = lista.filter((t) => !abiertos.some((x: any) => x.descripcion === t));
  return (
    <Modal titulo="Solicitar documentos al cliente" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault(); setError(""); setEnviando(true);
        try { onCreada(await api.post(`/evidencia/asuntos/${id}/solicitudes`, { ...f, mensaje: f.mensaje || null, documentos: lista })); }
        catch (err: any) { setError(err.message); }
        setEnviando(false);
      }}>
        {!p.catalogos.correo_configurado && <Aviso tipo="alerta">El envío de correos no está configurado: se creará el enlace para que usted lo copie y se lo mande al cliente.</Aviso>}
        <label className="block"><span className="etiqueta">Correo del cliente</span>
          <input className="campo" type="email" required maxLength={254} autoFocus value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="cliente@correo.com" /></label>
        <fieldset>
          <legend className="etiqueta">Documentos que necesita (opcional)</legend>
          {abiertos.length > 0 && <div className="mb-2 grid gap-1.5 sm:grid-cols-2">
            {abiertos.map((x: any) => (
              <label key={x.id} className={`flex cursor-pointer items-start gap-2 rounded-xl border p-2.5 text-sm ${lista.includes(x.descripcion) ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={lista.includes(x.descripcion)} onChange={() => alternar(x.descripcion)} />
                <span>{x.descripcion}<span className="block text-[11px] text-slate-500">De sus pendientes{x.responsable ? ` · ${x.responsable}` : ""}</span></span>
              </label>))}
          </div>}
          {extras.length > 0 && <ul className="mb-2 flex flex-wrap gap-1.5">{extras.map((t) => (
            <li key={t} className="flex items-center gap-1 rounded-full bg-turquesa-50 px-3 py-1 text-sm text-marino">{t}
              <button type="button" className="text-slate-500 hover:text-red-700" aria-label={`Quitar ${t}`} onClick={() => alternar(t)}>✕</button></li>))}</ul>}
          <div className="flex gap-2">
            <input className="campo" maxLength={200} placeholder="Agregar otro documento, p. ej. Comprobante de domicilio" value={otro}
              onChange={(e) => setOtro(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregar(); } }} />
            <button type="button" className="btn-sec" onClick={agregar}>Agregar</button>
          </div>
        </fieldset>
        <label className="block"><span className="etiqueta">Mensaje para el cliente (opcional)</span>
          <textarea className="campo" rows={3} maxLength={2000} value={f.mensaje} onChange={(e) => setF({ ...f, mensaje: e.target.value })} placeholder="Hola, para avanzar con su asunto necesitamos…" /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">El enlace vence en</span>
            <select className="campo" value={f.dias} onChange={(e) => setF({ ...f, dias: Number(e.target.value) })}>
              {[1, 3, 7, 14, 30].map((d) => <option key={d} value={d}>{d === 1 ? "1 día" : `${d} días`}{d === 7 ? " (recomendado)" : ""}</option>)}
            </select></label>
          <label className="flex items-start gap-2 self-end rounded-xl border border-crema-300 p-3 text-sm">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={f.requiere_codigo} onChange={(e) => setF({ ...f, requiere_codigo: e.target.checked })} />
            <span><b className="text-marino">Pedir código de verificación</b><span className="block text-xs text-slate-500">Antes de subir, el cliente escribe un código que le llega a ese correo. Recomendado.</span></span>
          </label>
        </div>
        <p className="text-xs text-slate-500">El cliente no verá notas internas, hechos, la matriz ni otros documentos del asunto. Podrá enviar hasta 20 archivos.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando}>{enviando ? "Enviando…" : "Enviar solicitud"}</button></div>
      </form>
    </Modal>
  );
}

function SolicitudCreada({ r, onCerrar }: any) {
  const [copiado, setCopiado] = useState(false);
  const s = r.solicitud;
  return (
    <Modal titulo="Solicitud creada" onCerrar={onCerrar}>
      <div className="space-y-3 text-sm">
        {r.correo.enviado ? <Aviso tipo="ok">Le enviamos el enlace a <b>{s.email}</b>{r.correo.prueba ? " (modo de prueba: el correo se guardó y no salió)" : ""}. Vence el {fechaHora(s.expira_en)}.</Aviso>
          : <Aviso tipo="alerta">No se pudo enviar el correo{r.correo.error ? `: ${r.correo.error}` : ""}. Copie el enlace y envíeselo usted.</Aviso>}
        <div>
          <span className="etiqueta">Enlace (se muestra solo esta vez)</span>
          <div className="flex gap-2">
            <input className="campo font-mono text-xs" readOnly value={r.enlace} onFocus={(e) => e.target.select()} />
            <button className="btn-sec whitespace-nowrap" onClick={() => navigator.clipboard?.writeText(r.enlace).then(() => setCopiado(true))}>{copiado ? "¡Copiado!" : "Copiar"}</button>
          </div>
          <p className="mt-1 text-xs text-slate-500">Compártalo solo con su cliente.{s.requiere_codigo ? " Aunque alguien más lo vea, necesitará el código que llega a su correo." : ""}</p>
        </div>
        <div className="flex justify-end"><button className="btn-primario" onClick={onCerrar}>Listo</button></div>
      </div>
    </Modal>
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

const COLOR_CALIDAD: Record<string, string> = { buena: "text-emerald-700", revisar: "text-amber-700", baja: "text-red-700" };
const TEXTO_CALIDAD: Record<string, string> = { buena: "Extracción clara", revisar: "Extracción por verificar", baja: "Extracción de baja calidad" };

/** Un hecho candidato por tarjeta: qué dice, quién lo afirma, la cita, la fuente y el tipo de dato. */
function TarjetaHecho({ h, ctx, sel, onSel, compacto }: any) {
  const { editor, accion, Fuente, enConflicto } = ctx;
  const c = h.calidad || {};
  const revisado = ["confirmado", "editado"].includes(h.estado);
  return (
    <article className={`tarjeta p-4 ${h.estado === "descartado" ? "opacity-70" : ""} ${sel ? "border-turquesa" : ""}`}>
      <div className="flex items-start gap-3">
        {onSel && editor && h.estado === "por_revisar" && (
          <input type="checkbox" className="mt-1 h-4 w-4 accent-turquesa" checked={!!sel} aria-label="Seleccionar hecho" onChange={(e) => onSel(e.target.checked)} />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Pastilla clase={COLOR_HECHO[h.estado]}>{h.estado_texto}</Pastilla>
            <Pastilla clase={COLOR_TIPO[h.tipo_dato] || COLOR_TIPO.otro}>{h.tipo_dato_texto}{h.tema_texto ? ` · ${h.tema_texto}` : ""}</Pastilla>
            {enConflicto?.has(h.id) && <Pastilla clase="bg-amber-100 text-amber-800">Posible diferencia por revisar</Pastilla>}
          </div>
          {h.atribucion && <p className="mt-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">{h.atribucion}…</p>}
          <p className={`mt-0.5 text-[15px] ${h.estado === "descartado" ? "line-through" : "text-slate-900"}`}>{h.descripcion}</p>
          {(h.valor_original || h.valor) && (
            <dl className="mt-2 inline-grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5 rounded-lg bg-crema/70 px-3 py-1.5 text-xs">
              {h.valor_original && <><dt className="text-slate-500">Texto original</dt><dd className="font-medium text-slate-800">«{h.valor_original}»</dd></>}
              {h.valor && <><dt className="text-slate-500">Dato normalizado</dt><dd className="font-marca font-bold text-marino">{h.valor}</dd></>}
            </dl>
          )}
          {!compacto && h.fragmento && h.fragmento !== h.descripcion && (
            <blockquote className="mt-2 border-l-2 border-crema-300 pl-3 text-xs italic text-slate-600">«{h.fragmento}»</blockquote>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
            <Fuente x={h} />
            {h.origen === "manual" ? <span>Capturado por {h.creado_por || "una persona"}</span>
              : <span className={COLOR_CALIDAD[c.nivel]} title={c.motivo || ""}>{TEXTO_CALIDAD[c.nivel]}</span>}
            {h.revisado_por && h.estado !== "por_revisar" && <span>{h.estado === "descartado" ? "Descartó" : "Revisó"}: {h.revisado_por}, {fechaHora(h.revisado_en)}</span>}
            <button className="font-semibold text-slate-500 hover:text-marino hover:underline" onClick={() => ctx.historial(h)}>Historial</button>
          </div>
          {!compacto && h.origen === "automatico" && (c.identificado?.length > 0 || c.no_identificado?.length > 0 || c.motivo) && (
            <p className="mt-1 text-xs text-slate-500">
              {c.identificado?.length > 0 && <>Se identificó: {c.identificado.join(", ")}. </>}
              {c.no_identificado?.length > 0 && <>No se identificó: {c.no_identificado.join(", ")}. </>}
              {c.motivo && <span className={COLOR_CALIDAD[c.nivel]}>{c.motivo} </span>}
              {c.lectura}
            </p>
          )}
          {!h.documento_id && <p className="mt-1 text-xs font-semibold text-red-700">No puede confirmarse sin una fuente.</p>}
        </div>
        {editor && (
          <div className="flex shrink-0 flex-col gap-1.5">
            {h.estado === "por_revisar" && <button className="btn-primario" disabled={!h.documento_id} title="Confirma que el dato está bien tomado del documento; no que sea verdadero ni que esté probado"
              onClick={() => accion(() => api.post(`/evidencia/hechos/${h.id}/confirmar`), "Hecho confirmado por usted.")}>Confirmar</button>}
            {h.estado !== "descartado" && <button className="btn-sec" onClick={() => ctx.editar(h)}>Editar</button>}
            {h.estado !== "descartado" && <button className="btn-sec" onClick={() => accion(() => api.post(`/evidencia/hechos/${h.id}/descartar`), "Hecho descartado.")}>Descartar</button>}
            {h.estado !== "descartado" && <button className="btn-sec text-xs" onClick={() => accion(() => api.post(`/evidencia/hechos/${h.id}/no_relevante`), "Marcado como no relevante para este asunto.")}>No es relevante para este asunto</button>}
            {revisado && <button className="btn-turquesa text-xs" onClick={() => ctx.vincular(h)}>Vincular con un punto de evidencia</button>}
            {h.estado !== "por_revisar" && <button className="btn-sec text-xs" onClick={() => accion(() => api.post(`/evidencia/hechos/${h.id}/reabrir`), "Devuelto a revisión.")}>Volver a revisión</button>}
          </div>
        )}
      </div>
    </article>
  );
}

function Hechos(ctx: any) {
  const { p, id, editor, accion } = ctx;
  const [filtro, setFiltro] = useState<string>(p.resumen.hechos.por_revisar ? "por_revisar" : "todos");
  const [doc, setDoc] = useState<string>("");
  const [tipo, setTipo] = useState<string>("");
  const [verBaja, setVerBaja] = useState(false);
  const [sel, setSel] = useState<number[]>([]);
  const enConflicto = new Set(p.contradicciones.filter((c: any) => c.estado === "pendiente" || c.contradiccion).flatMap((c: any) => c.hechos));
  const base = p.hechos.filter((h: any) => (filtro === "todos" || h.estado === filtro) && (!doc || String(h.documento_id) === doc) && (!tipo || h.tipo_dato === tipo));
  const baja = base.filter((h: any) => h.estado === "por_revisar" && h.calidad?.nivel === "baja");
  const visibles = verBaja ? base : base.filter((h: any) => !baja.includes(h));
  const filtros: [string, string][] = [["por_revisar", "Propuestos por Nomira"], ["confirmado", "Confirmados"], ["editado", "Editados"], ["descartado", "Descartados"], ["todos", "Todos"]];
  const cuenta = (k: string) => (k === "todos" ? p.hechos.length : p.resumen.hechos[k]);
  const masivo = (accionM: string) => accion(() => api.post(`/evidencia/asuntos/${id}/hechos/${accionM}`, { ids: sel }),
    accionM === "confirmar" ? `${sel.length} hecho(s) confirmados por usted.` : `${sel.length} hecho(s) descartados.`).then(() => setSel([]));
  const c2 = { ...ctx, enConflicto };
  return (
    <div className="space-y-4">
      <Aviso tipo="info">Cada tarjeta es un <b>hecho candidato</b> que Nomira encontró en un documento. «Confirmar» solo indica que una persona revisó que el dato está bien tomado del documento: no lo vuelve verdadero ni probado.</Aviso>
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
          <select className="campo w-auto py-1.5" value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Filtrar por tipo de dato">
            <option value="">Todos los tipos</option>
            {Object.entries(p.catalogos.tipos_dato).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
          </select>
        </div>
        {editor && <button className="btn-turquesa" onClick={() => ctx.editar({ nuevo: true })}>+ Agregar hecho</button>}
      </div>
      {editor && sel.length > 0 && (
        <div className="sticky top-2 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-turquesa bg-turquesa-50 p-3 shadow-suave">
          <span className="text-sm font-semibold text-marino">{sel.length} seleccionado(s)</span>
          <button className="btn-primario" onClick={() => masivo("confirmar")}>Confirmar seleccionados</button>
          <button className="btn-sec" onClick={() => masivo("descartar")}>Descartar seleccionados</button>
          <button className="text-sm text-slate-600 hover:underline" onClick={() => setSel([])}>Quitar selección</button>
        </div>
      )}
      {baja.length > 0 && (
        <button className="text-sm font-semibold text-slate-600 hover:underline" onClick={() => setVerBaja(!verBaja)}>
          {verBaja ? "Ocultar" : "Mostrar"} {baja.length} propuesta(s) de baja calidad (frases fragmentadas, ilegibles o texto legal genérico)
        </button>
      )}
      {visibles.length === 0 && <div className="tarjeta p-8 text-center text-sm text-slate-500">{p.hechos.length ? "No hay hechos en este filtro." : "Aún no hay hechos. Suba documentos o agregue uno manualmente."}</div>}
      {editor && filtro === "por_revisar" && visibles.length > 1 && (
        <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={sel.length === visibles.length}
          onChange={(e) => setSel(e.target.checked ? visibles.map((h: any) => h.id) : [])} /> Seleccionar los {visibles.length} visibles</label>
      )}
      <div className="space-y-3">
        {visibles.map((h: any) => <TarjetaHecho key={h.id} h={h} ctx={c2} sel={sel.includes(h.id)}
          onSel={(v: boolean) => setSel(v ? [...sel, h.id] : sel.filter((x) => x !== h.id))} />)}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Requiere tu atención

function Atencion(ctx: any) {
  const { p, editor, accion, ir, verFuente } = ctx;
  const r = p.resumen;
  const [clasificar, setClasificar] = useState<any>(null);
  const porRevisar = p.hechos.filter((h: any) => h.estado === "por_revisar" && h.calidad?.nivel !== "baja");
  const recibidos = p.documentos.filter((d: any) => d.estado === "recibido");
  const sinClasificar = p.documentos.filter((d: any) => !d.tipo && !["pendiente", "procesando", "recibido"].includes(d.estado));
  const problemas = p.documentos.filter((d: any) => ["error", "requiere_revision"].includes(d.estado));
  const diferencias = p.contradicciones.filter((c: any) => c.estado === "pendiente");
  const pendientes = p.pendientes.filter((x: any) => x.vencido || x.proximo);
  const puntos = p.puntos.filter((x: any) => !x.vinculos.length);
  const enConflicto = new Set(diferencias.flatMap((c: any) => c.hechos));
  const vacio = !recibidos.length && !diferencias.length && !pendientes.length && !porRevisar.length && !sinClasificar.length && !puntos.length && !problemas.length;
  const Seccion = ({ titulo, n, destino, children, nota }: any) => (
    <section className="tarjeta overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 bg-crema/40 px-5 py-3">
        <h2 className="font-semibold text-marino">{titulo} <span className="ml-1 rounded-full bg-amber-100 px-2 text-xs text-amber-800">{n}</span></h2>
        {destino && <button className="text-sm font-semibold text-turquesa-700 hover:underline" onClick={() => ir(destino)}>Ver todos →</button>}
      </div>
      {nota && <p className="px-5 pt-3 text-xs text-slate-500">{nota}</p>}
      <div className="space-y-3 p-4">{children}</div>
    </section>
  );
  if (vacio) return <div className="tarjeta p-10 text-center"><p className="font-marca text-lg font-bold text-marino">Todo al día</p><p className="text-sm text-slate-500">No hay documentos, hechos, diferencias ni pendientes que requieran su atención en este asunto.</p></div>;
  return (
    <div className="space-y-5">
      {recibidos.length > 0 && (
        <Seccion titulo="Documentos enviados por el cliente por aceptar" n={recibidos.length} destino="documentos"
          nota="No se leen ni se analizan hasta que usted los acepte. Nomira no tiene antivirus: revíselos antes de abrirlos fuera de Nomira.">
          {recibidos.slice(0, 5).map((d: any) => (
            <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span><b>{d.nombre}</b>{d.solicitado_como && <span className="text-slate-500"> · enviado como «{d.solicitado_como}»</span>} <span className="text-xs text-slate-400">{fechaHora(d.creado_en)}</span></span>
              <span className="flex gap-1.5">
                <button className="btn-sec" onClick={() => verFuente({ documento_id: d.id, pagina: 1 })}>Ver</button>
                {editor && <button className="btn-primario" onClick={() => accion(() => api.post(`/evidencia/documentos/${d.id}/aceptar`), `«${d.nombre}» aceptado: Nomira lo está leyendo.`)}>Aceptar y leer</button>}
                {editor && <button className="btn-peligro" onClick={() => { if (confirm(`¿Rechazar «${d.nombre}»? Se borrará del asunto.`)) accion(() => api.borrar(`/evidencia/documentos/${d.id}`), "Documento rechazado."); }}>Rechazar</button>}
              </span>
            </div>))}
        </Seccion>
      )}
      {diferencias.length > 0 && (
        <Seccion titulo="Posibles diferencias entre fuentes sin resolver" n={diferencias.length} destino="diferencias">
          {diferencias.slice(0, 3).map((c: any) => <TarjetaDiferencia key={c.par} c={c} ctx={ctx} />)}
        </Seccion>
      )}
      {pendientes.length > 0 && (
        <Seccion titulo="Pendientes vencidos o por vencer" n={pendientes.length} destino="pendientes">
          {pendientes.map((x: any) => (
            <div key={x.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span><b>{x.descripcion}</b> <span className={x.vencido ? "font-semibold text-red-700" : "text-amber-700"}>· {x.vencido ? "venció" : "vence"} el {fecha(x.fecha_seguimiento)}</span>{x.responsable && <span className="text-slate-500"> · {x.responsable}</span>}</span>
              {editor && <span className="flex gap-1.5">
                <button className="btn-sec" onClick={() => accion(() => api.patch(`/evidencia/pendientes/${x.id}`, { estado: "recibido" }), "Pendiente marcado como recibido.")}>Marcar recibido</button>
                {x.estado === "pendiente" && <button className="btn-sec" onClick={() => accion(() => api.patch(`/evidencia/pendientes/${x.id}`, { estado: "solicitado" }), "Pendiente marcado como solicitado.")}>Marcar solicitado</button>}
              </span>}
            </div>))}
        </Seccion>
      )}
      {porRevisar.length > 0 && (
        <Seccion titulo="Hechos propuestos por revisar" n={porRevisar.length} destino="hechos">
          {porRevisar.slice(0, 3).map((h: any) => <TarjetaHecho key={h.id} h={h} ctx={{ ...ctx, enConflicto }} compacto />)}
        </Seccion>
      )}
      {(sinClasificar.length > 0 || problemas.length > 0) && (
        <Seccion titulo="Documentos por clasificar o con problemas de lectura" n={sinClasificar.length + problemas.filter((d: any) => !sinClasificar.includes(d)).length} destino="documentos">
          {[...problemas, ...sinClasificar.filter((d: any) => !problemas.includes(d))].slice(0, 6).map((d: any) => (
            <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span><b>{d.nombre}</b> {d.error ? <span className="text-xs text-amber-800">· {d.error}</span> : d.tipo_sugerido ? <span className="text-slate-500">· Nomira sugiere «{d.tipo_sugerido}»</span> : <span className="text-slate-500">· sin clasificar</span>}</span>
              <span className="flex gap-1.5">
                <button className="btn-sec" onClick={() => verFuente({ documento_id: d.id, pagina: 1 })}>Ver</button>
                {editor && !d.tipo && <button className="btn-sec" onClick={() => setClasificar(d)}>Clasificar</button>}
                {editor && ["error", "requiere_revision"].includes(d.estado) && <button className="btn-sec" onClick={() => accion(() => api.post(`/evidencia/documentos/${d.id}/reprocesar`), "Volviendo a leer el documento…")}>Volver a leer</button>}
              </span>
            </div>))}
        </Seccion>
      )}
      {puntos.length > 0 && (
        <Seccion titulo="Puntos de la matriz sin evidencia vinculada" n={puntos.length} destino="matriz">
          {puntos.map((x: any) => <div key={x.id} className="flex items-center justify-between gap-2 text-sm"><b>{x.descripcion}</b>
            <button className="btn-sec" onClick={() => ir("matriz")}>Vincular evidencia</button></div>)}
        </Seccion>
      )}
      {clasificar && <Clasificar d={clasificar} tipos={p.catalogos.tipos_documento} onCerrar={() => setClasificar(null)}
        onGuardar={(datos: any) => accion(() => api.patch(`/evidencia/documentos/${clasificar.id}`, datos), "Clasificación guardada.").then((x: any) => { if (x) setClasificar(null); })} />}
    </div>
  );
}

// ------------------------------------------------------------------ Posibles diferencias

const COLOR_DECISION: Record<string, string> = {
  eventos_distintos: "bg-sky-100 text-sky-800", aclarada: "bg-emerald-100 text-emerald-800", contradiccion: "bg-red-100 text-red-800", no_aplica: "bg-slate-200 text-slate-600",
};

function TarjetaDiferencia({ c, ctx }: any) {
  const { p, id, editor, accion, Fuente } = ctx;
  const porId = Object.fromEntries(p.hechos.map((h: any) => [h.id, h]));
  const [nota, setNota] = useState("");
  const decidir = (decision: string | null) => accion(() => api.post(`/evidencia/asuntos/${id}/diferencias`, { par: c.par, decision, nota: nota || null }),
    decision ? `Decisión registrada: ${p.catalogos.decisiones[decision]}.` : "La diferencia volvió a «por revisar».");
  return (
    <div className={`rounded-xl border p-4 ${c.estado === "pendiente" ? "border-amber-300 bg-amber-50/40" : "border-crema-300"}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {c.estado === "pendiente" ? <Pastilla clase="bg-amber-100 text-amber-800">Posible diferencia por revisar</Pastilla>
          : <Pastilla clase={COLOR_DECISION[c.decision.decision]}>{c.decision_texto}</Pastilla>}
        {c.tema_texto && <span className="text-xs font-semibold text-slate-600">{c.tema_texto}</span>}
        {c.decision?.por_nombre && <span className="text-xs text-slate-500">Decidió {c.decision.por_nombre}, {fechaHora(c.decision.en)}{c.decision.nota && ` · «${c.decision.nota}»`}</span>}
      </div>
      <p className="mb-3 text-sm text-slate-700">{c.explicacion}</p>
      <div className="grid gap-3 md:grid-cols-2">
        {c.hechos.map((hid: number, i: number) => {
          const h = porId[hid];
          if (!h) return null;
          return (
            <div key={hid} className="rounded-xl bg-white p-3 ring-1 ring-crema-300">
              <div className="etiqueta">Fuente {i ? "B" : "A"}{h.atribucion ? ` · ${h.atribucion}` : ""}</div>
              <div className="font-marca text-lg font-extrabold text-marino">{c.difieren.includes("importe") && h.importe ? mxn(h.importe) : h.valor || (h.fecha ? fecha(h.fecha) : "—")}</div>
              <p className="mt-1 text-sm">{h.descripcion}</p>
              {h.fragmento && <blockquote className="mt-1 border-l-2 border-crema-300 pl-2 text-xs italic text-slate-600">«{h.fragmento}»</blockquote>}
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 text-xs"><Fuente x={h} /><span className="text-slate-500">{h.estado_texto}</span>
                {editor && <button className="font-semibold text-turquesa-700 hover:underline" onClick={() => ctx.editar(h)}>Corregir este dato</button>}</div>
            </div>
          );
        })}
      </div>
      {editor && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {c.estado === "pendiente" ? (
            <>
              <input className="campo max-w-xs py-1.5 text-sm" maxLength={300} placeholder="Nota (opcional)" value={nota} onChange={(e) => setNota(e.target.value)} aria-label="Nota de la decisión" />
              {Object.entries(p.catalogos.decisiones).map(([k, t]: any) => (
                <button key={k} className={k === "contradiccion" ? "btn bg-red-600 text-white hover:bg-red-700" : "btn-sec"} onClick={() => decidir(k)}>{t}</button>))}
            </>
          ) : <button className="btn-sec" onClick={() => decidir(null)}>Volver a revisar</button>}
        </div>
      )}
    </div>
  );
}

function Diferencias(ctx: any) {
  const { p } = ctx;
  const pendientes = p.contradicciones.filter((c: any) => c.estado === "pendiente");
  const resueltas = p.contradicciones.filter((c: any) => c.estado === "resuelta");
  return (
    <div className="space-y-4">
      <Aviso tipo="info">Nomira compara fechas, cantidades y nombres del <b>mismo dato</b> entre documentos distintos (nunca la fecha de un documento contra la del evento que describe). Una diferencia no es una contradicción definitiva: usted decide qué es. Su decisión no cambia ningún hecho ni la matriz, y queda en el historial.</Aviso>
      {pendientes.length === 0 && <div className="tarjeta p-8 text-center text-sm text-slate-500">{resueltas.length ? "No hay diferencias pendientes." : "Nomira no encontró diferencias entre las fuentes de este asunto."}</div>}
      {pendientes.map((c: any) => <TarjetaDiferencia key={c.par} c={c} ctx={ctx} />)}
      {resueltas.length > 0 && (
        <section className="space-y-3">
          <h2 className="mt-6 text-sm font-bold uppercase tracking-wider text-slate-400">Ya decididas ({resueltas.length})</h2>
          {resueltas.map((c: any) => <TarjetaDiferencia key={c.par} c={c} ctx={ctx} />)}
        </section>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Buscar e historial

function Buscar({ id, verFuente }: any) {
  const [q, setQ] = useState("");
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [buscando, setBuscando] = useState(false);
  return (
    <div className="space-y-4">
      <form className="flex flex-wrap gap-2" onSubmit={async (e) => {
        e.preventDefault(); setError(""); setBuscando(true);
        try { setR(await api.get(`/evidencia/asuntos/${id}/buscar?q=${encodeURIComponent(q)}`)); } catch (err: any) { setError(err.message); }
        setBuscando(false);
      }}>
        <input className="campo max-w-xl" type="search" minLength={2} maxLength={100} required value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en el texto de los documentos (sin importar acentos)" aria-label="Texto a buscar" />
        <button className="btn-primario" disabled={buscando}>{buscando ? "Buscando…" : "Buscar"}</button>
      </form>
      <p className="text-xs text-slate-500">Busca en el texto que Nomira leyó de los documentos de este asunto (incluido el OCR, que puede tener errores). No incluye documentos del cliente aún no aceptados ni los restringidos que usted no puede ver.</p>
      <Aviso>{error}</Aviso>
      {r && (r.resultados.length === 0 ? <div className="tarjeta p-8 text-center text-sm text-slate-500">Sin resultados para «{r.termino}».</div> : (
        <div className="space-y-2">
          <p className="text-sm text-slate-600">{r.total} coincidencia(s) en {r.resultados.length} página(s).</p>
          {r.resultados.map((x: any, i: number) => (
            <button key={i} className="tarjeta block w-full p-3 text-left transition hover:border-turquesa"
              onClick={() => verFuente({ documento_id: x.documento_id, pagina: x.pagina, fragmento: x.antes.replace(/^…/, "") + x.coincidencia + x.despues.replace(/…$/, "") })}>
              <div className="text-xs font-semibold text-turquesa-700">D{x.documento_id} · {x.documento}, p. {x.pagina}{x.coincidencias > 1 ? ` · ${x.coincidencias} coincidencias` : ""} ↗</div>
              <p className="mt-1 text-sm text-slate-700">{x.antes}<mark className="rounded bg-turquesa/30 px-0.5">{x.coincidencia}</mark>{x.despues}</p>
            </button>))}
        </div>
      ))}
    </div>
  );
}

function HistorialAsunto({ id }: any) {
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`/evidencia/asuntos/${id}/historial`).then(setLista).catch((e) => setError(e.message)); }, [id]);
  const det = (d: any) => [d.decision && `Decisión: ${d.decision}`, d.relacion && `Relación: ${d.relacion}`, d.visibilidad && `Visibilidad: ${d.visibilidad}`,
    d.despues && typeof d.despues === "string" && `Estado: ${d.despues}`, d.email && `Para: ${d.email}`, d.nota && `Nota: ${d.nota}`,
    Array.isArray(d.campos) && d.campos.length > 0 && `Campos: ${d.campos.join(", ")}`].filter(Boolean).join(" · ");
  return (
    <div className="tarjeta overflow-x-auto">
      <Aviso>{error}</Aviso>
      {!lista && !error && <p className="p-5 text-sm text-slate-500">Cargando…</p>}
      {lista && lista.length === 0 && <p className="p-5 text-sm text-slate-500">Sin movimientos registrados.</p>}
      {lista && lista.length > 0 && (
        <table className="tabla">
          <thead><tr><th>Fecha</th><th>Quién</th><th>Qué hizo</th><th>Detalle</th></tr></thead>
          <tbody>{lista.map((x, i) => (
            <tr key={i}><td className="whitespace-nowrap">{fechaHora(x.fecha)}</td><td>{x.usuario}</td><td className="font-semibold">{x.accion}</td>
              <td className="max-w-md text-xs text-slate-600">{det(x.detalle || {})}</td></tr>))}</tbody>
        </table>
      )}
    </div>
  );
}

function Historial({ h, onCerrar }: any) {
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`/evidencia/hechos/${h.id}/historial`).then(setLista).catch((e) => setError(e.message)); }, [h.id]);
  const valor = (v: any) => (v == null || v === "" ? "—" : Array.isArray(v) ? v.join(", ") : String(v));
  return (
    <Modal titulo="Historial del dato" onCerrar={onCerrar} ancho="max-w-xl">
      <p className="mb-3 text-sm text-slate-700">{h.descripcion}</p>
      <Aviso>{error}</Aviso>
      {!lista && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      <ol className="relative ml-2 space-y-3 border-l-2 border-crema-300 pl-5">
        {lista?.map((x, i) => (
          <li key={i} className="relative text-sm">
            <span className="absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-white bg-turquesa" aria-hidden />
            <div className="font-semibold text-marino">{x.accion}</div>
            <div className="text-xs text-slate-500">{x.usuario || "Nomira"} · {fechaHora(x.fecha)}</div>
            {x.detalle?.antes && Object.keys(x.detalle.antes).map((k) => (
              <div key={k} className="text-xs text-slate-600">{k}: <span className="line-through">{valor(x.detalle.antes[k])}</span> → <b>{valor(x.detalle.despues?.[k])}</b></div>))}
          </li>))}
      </ol>
    </Modal>
  );
}

function EditarHecho({ h, documentos, tipos, onCerrar, onGuardar }: any) {
  const [f, setF] = useState({
    tipo_dato: h?.tipo_dato || "fecha_evento",
    descripcion: h?.descripcion || "", fecha: h?.fecha || "", personas: (h?.personas || []).join(", "), importe: h?.importe || "",
    dato: h?.dato || "", documento_id: h?.documento_id ? String(h.documento_id) : "", pagina: h?.pagina ? String(h.pagina) : "",
  });
  const cambiar = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const doc = documentos.find((d: any) => String(d.id) === f.documento_id);
  return (
    <Modal titulo={h ? "Editar hecho" : "Agregar hecho"} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        onGuardar({ tipo_dato: f.tipo_dato, descripcion: f.descripcion, fecha: f.fecha || null, importe: f.importe || null, dato: f.dato || null,
          personas: f.personas.split(",").map((x: string) => x.trim()).filter(Boolean),
          documento_id: f.documento_id ? Number(f.documento_id) : null, pagina: f.pagina ? Number(f.pagina) : null });
      }}>
        {h?.original && h.origen === "automatico" && <Aviso tipo="info">Propuesta original: «{h.original.descripcion}»{h.original.fecha && ` · ${fecha(h.original.fecha)}`}</Aviso>}
        <label className="block"><span className="etiqueta">Tipo de dato</span>
          <select className="campo" value={f.tipo_dato} onChange={cambiar("tipo_dato")}>
            {Object.entries(tipos || {}).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
          </select>
          {f.tipo_dato === "fecha_documento" && <span className="mt-1 block text-xs text-slate-500">La fecha en que se hizo, firmó o emitió el documento no aparece en la cronología de los hechos.</span>}</label>
        <label className="block"><span className="etiqueta">Descripción</span>
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
        <p className="text-xs text-slate-500">{h ? "Al guardar queda como «Editado y validado» si conserva su documento fuente. La propuesta original y el cambio quedan en el historial."
          : "Con documento fuente queda validado por usted. Sin fuente, queda por revisar."}</p>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Guardar</button></div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ Cronología

function Cronologia({ p, Fuente, ir }: any) {
  const ev = p.cronologia.eventos;
  const porAnio: Record<string, any[]> = {};
  for (const e of ev) (porAnio[e.fecha.slice(0, 4)] ||= []).push(e);
  const revision = (h: any) => h.origen === "manual" ? `Capturado por ${h.creado_por || "usuario"}`
    : h.estado === "editado" ? `Editado por ${h.revisado_por || "usuario"}` : `Confirmado por ${h.revisado_por || "usuario"}`;
  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-500">Solo hechos confirmados o editados por una persona. La fecha en que se hizo un documento no aparece como evento. {p.resumen.hechos.por_revisar > 0 && <>Hay {p.resumen.hechos.por_revisar} propuesta(s) sin revisar que no aparecen aquí.</>}</p>
      {p.resumen.diferencias_pendientes > 0 && <Aviso tipo="alerta">Hay {p.resumen.diferencias_pendientes} posible(s) diferencia(s) entre fuentes sin resolver. <button className="font-semibold underline" onClick={() => ir("diferencias")}>Revisarlas</button></Aviso>}
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
                    <Pastilla clase={COLOR_TIPO[h.tipo_dato] || COLOR_TIPO.otro}>{h.tipo_dato_texto}{h.tema_texto ? ` · ${h.tema_texto}` : ""}</Pastilla>
                    {h.contradicciones.length > 0 && <button onClick={() => ir("diferencias")}><Pastilla clase="bg-amber-100 text-amber-800">Diferencia con otra fuente</Pastilla></button>}
                  </div>
                  {h.atribucion && <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{h.atribucion}…</p>}
                  <p className="mt-0.5 text-sm text-slate-800">{h.descripcion}</p>
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

const COLOR_RELACION: Record<string, string> = {
  sin_evaluar: "bg-slate-100 text-slate-600", apoya: "bg-emerald-100 text-emerald-800", contradice: "bg-red-100 text-red-800", no_basta: "bg-amber-100 text-amber-800",
};

function Matriz({ p, id, editor, accion, Fuente }: any) {
  const [nuevo, setNuevo] = useState("");
  const [vincular, setVincular] = useState<any>(null);
  const revisados = p.hechos.filter((h: any) => ["confirmado", "editado"].includes(h.estado) && h.documento_id);
  return (
    <div className="space-y-4">
      <Aviso tipo="info">Agregue los hechos que necesita acreditar y vincule hechos confirmados o documentos. Indique si cada fuente <b>apoya</b>, <b>contradice</b> o <b>no basta</b>. El estado del punto lo decide usted: un archivo vinculado no hace que un punto esté respaldado, y Nomira no evalúa relevancia ni suficiencia.</Aviso>
      {editor && (
        <form className="tarjeta flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); accion(() => api.post(`/evidencia/asuntos/${id}/puntos`, { descripcion: nuevo }), "Punto agregado.").then((r: any) => { if (r) setNuevo(""); }); }}>
          <label className="block grow"><span className="etiqueta">Hecho que se busca acreditar</span>
            <input className="campo" required minLength={3} maxLength={2000} value={nuevo} onChange={(e) => setNuevo(e.target.value)} placeholder="p. ej. Fecha de separación de las partes" /></label>
          <button className="btn-turquesa">Agregar a la matriz</button>
        </form>
      )}
      {p.puntos.length === 0 && <div className="tarjeta p-10 text-center text-sm text-slate-500">La matriz está vacía.</div>}
      {p.puntos.map((pt: any) => {
        const grupos = ["apoya", "contradice", "no_basta", "sin_evaluar"].map((k) => [k, pt.vinculos.filter((v: any) => v.relacion === k)] as const).filter(([, vs]) => vs.length);
        return (
          <section key={pt.id} className="tarjeta p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <h3 className="font-marca text-lg font-bold text-marino">{pt.descripcion}</h3>
                {pt.estado_decidido_por ? <p className="text-xs text-slate-500">Estado decidido por {pt.estado_decidido_por}, {fechaHora(pt.estado_decidido_en)}</p>
                  : <p className="text-xs font-semibold text-amber-700">Sin decisión del abogado</p>}
              </div>
              <div className="flex items-center gap-2">
                {editor ? (
                  <select className={`campo w-auto font-semibold ${COLOR_PUNTO[pt.estado]}`} value={pt.estado} aria-label="Estado del punto"
                    onChange={(e) => accion(() => api.patch(`/evidencia/puntos/${pt.id}`, { estado: e.target.value }), "Estado actualizado.")}>
                    {Object.entries(p.catalogos.estados_punto).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
                  </select>
                ) : <Pastilla clase={COLOR_PUNTO[pt.estado]}>{pt.estado_texto}</Pastilla>}
                {editor && <button className="btn-peligro" aria-label="Quitar punto" onClick={() => { if (confirm("¿Quitar este punto de la matriz? Las fuentes vinculadas no se borran.")) accion(() => api.borrar(`/evidencia/puntos/${pt.id}`), "Punto eliminado."); }}>✕</button>}
              </div>
            </div>
            {pt.sugerencia.estado !== pt.estado && (
              <p className="mt-2 rounded-lg bg-crema/70 px-3 py-2 text-xs text-slate-600">
                <b>Sugerencia del sistema (no es una decisión):</b> {p.catalogos.estados_punto[pt.sugerencia.estado]}. {pt.sugerencia.motivo}
                {editor && <button className="ml-2 font-semibold text-turquesa-700 hover:underline" onClick={() => accion(() => api.patch(`/evidencia/puntos/${pt.id}`, { estado: pt.sugerencia.estado }), "Estado actualizado.")}>Usar</button>}
              </p>
            )}
            {pt.vinculos.length === 0 && <p className="mt-3 text-sm text-slate-500">Sin evidencia vinculada.</p>}
            {grupos.map(([k, vs]) => (
              <div key={k} className="mt-3">
                <div className="etiqueta">{k === "sin_evaluar" ? "Fuentes sin evaluar" : `Fuentes que ${p.catalogos.relaciones[k].toLowerCase()}`}</div>
                <ul className="space-y-2">
                  {vs.map((v: any) => (
                    <li key={v.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-crema-300 p-3 text-sm">
                      <div className="min-w-0 flex-1">
                        {v.hecho ? <p>{v.hecho.fecha && <b className="text-marino">{fecha(v.hecho.fecha)} · </b>}{v.hecho.descripcion}</p> : <p className="text-slate-600">Documento completo o página</p>}
                        <div className="mt-1 flex flex-wrap gap-x-3 text-xs"><Fuente x={v.hecho || v} />{v.nota && <span className="text-slate-500">{v.nota}</span>}
                          {v.relacion_por && <span className="text-slate-500">Evaluó {v.relacion_por}, {fechaHora(v.relacion_en)}</span>}</div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {editor ? (
                          <select className={`campo w-auto py-1 text-xs font-semibold ${COLOR_RELACION[v.relacion]}`} value={v.relacion} aria-label="Qué hace esta fuente respecto al punto"
                            onChange={(e) => accion(() => api.patch(`/evidencia/vinculos/${v.id}`, { relacion: e.target.value }), "Evaluación guardada.")}>
                            {Object.entries(p.catalogos.relaciones).map(([k2, t]: any) => <option key={k2} value={k2}>{t}</option>)}
                          </select>
                        ) : <Pastilla clase={COLOR_RELACION[v.relacion]}>{v.relacion_texto}</Pastilla>}
                        {editor && <button className="text-xs text-red-700 hover:underline" onClick={() => accion(() => api.borrar(`/evidencia/vinculos/${v.id}`), "Vínculo quitado.")}>Quitar</button>}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {pt.vinculos_restringidos > 0 && <p className="mt-2 text-xs text-slate-500">{pt.vinculos_restringidos} fuente(s) restringida(s) no visibles para su usuario.</p>}
            {editor && <button className="mt-3 text-sm font-semibold text-turquesa-700 hover:underline" onClick={() => setVincular(pt)}>+ Vincular hechos o documentos</button>}
          </section>
        );
      })}
      {vincular && <Vincular punto={vincular} hechos={revisados} documentos={p.documentos.filter((d: any) => d.estado !== "recibido")} relaciones={p.catalogos.relaciones}
        onCerrar={() => setVincular(null)}
        onGuardar={async (lista: any[]) => {
          const r = await accion(async () => { for (const x of lista) await api.post(`/evidencia/puntos/${vincular.id}/vinculos`, x); }, `${lista.length} fuente(s) vinculada(s).`);
          if (r) setVincular(null);
        }} />}
    </div>
  );
}

function Vincular({ punto, hechos, documentos, relaciones, onCerrar, onGuardar }: any) {
  const ya = new Set(punto.vinculos.map((v: any) => v.hecho_id).filter(Boolean));
  const [selH, setSelH] = useState<number[]>([]);
  const [selD, setSelD] = useState<Record<number, string>>({});
  const [relacion, setRelacion] = useState("sin_evaluar");
  const [nota, setNota] = useState("");
  const [buscar, setBuscar] = useState("");
  const lista = hechos.filter((h: any) => !ya.has(h.id) && (!buscar || h.descripcion.toLowerCase().includes(buscar.toLowerCase())));
  const total = selH.length + Object.keys(selD).length;
  return (
    <Modal titulo={`Vincular evidencia: ${punto.descripcion}`} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-4" onSubmit={(e) => {
        e.preventDefault();
        onGuardar([...selH.map((h) => ({ hecho_id: h, relacion, nota: nota || null })),
          ...Object.entries(selD).map(([d, pag]) => ({ documento_id: Number(d), pagina: pag ? Number(pag) : null, relacion, nota: nota || null }))]);
      }}>
        <fieldset>
          <legend className="etiqueta">Hechos confirmados o editados</legend>
          {hechos.length === 0 ? <Aviso tipo="alerta">Aún no hay hechos confirmados. Confírmelos en la pestaña «Hechos».</Aviso> : (
            <>
              <input className="campo mb-2" placeholder="Buscar hecho" value={buscar} onChange={(e) => setBuscar(e.target.value)} />
              <div className="max-h-56 space-y-1.5 overflow-auto">
                {lista.map((h: any) => (
                  <label key={h.id} className={`flex cursor-pointer gap-2 rounded-xl border p-2.5 text-sm ${selH.includes(h.id) ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
                    <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={selH.includes(h.id)} onChange={(e) => setSelH(e.target.checked ? [...selH, h.id] : selH.filter((x) => x !== h.id))} />
                    <span>{h.fecha && <b className="text-marino">{fecha(h.fecha)} · </b>}{h.descripcion}</span>
                  </label>))}
              </div>
            </>
          )}
        </fieldset>
        <fieldset>
          <legend className="etiqueta">Documentos (completos o una página)</legend>
          <div className="max-h-44 space-y-1.5 overflow-auto">
            {documentos.map((d: any) => (
              <div key={d.id} className={`flex items-center gap-2 rounded-xl border p-2 text-sm ${d.id in selD ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
                <input type="checkbox" className="h-4 w-4 accent-turquesa" aria-label={`Vincular ${d.nombre}`} checked={d.id in selD}
                  onChange={(e) => { const x = { ...selD }; if (e.target.checked) x[d.id] = ""; else delete x[d.id]; setSelD(x); }} />
                <span className="grow">D{d.id} · {d.nombre}</span>
                {d.id in selD && <input className="campo w-24 py-1" type="number" min={1} max={d.paginas || 10000} placeholder="Página" value={selD[d.id]} onChange={(e) => setSelD({ ...selD, [d.id]: e.target.value })} />}
              </div>))}
          </div>
        </fieldset>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">Estas fuentes…</span>
            <select className="campo" value={relacion} onChange={(e) => setRelacion(e.target.value)}>
              {Object.entries(relaciones).map(([k, t]: any) => <option key={k} value={k}>{k === "sin_evaluar" ? "Evaluar después" : t}</option>)}
            </select></label>
          <label className="block"><span className="etiqueta">Nota (opcional)</span><input className="campo" maxLength={500} value={nota} onChange={(e) => setNota(e.target.value)} /></label>
        </div>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={!total}>Vincular {total || ""}</button></div>
      </form>
    </Modal>
  );
}

/** Desde un hecho confirmado: elegir (o crear) el punto de la matriz al que se vincula. */
function VincularHecho({ h, p, id, accion, onCerrar }: any) {
  const [punto, setPunto] = useState<string>(p.puntos[0] ? String(p.puntos[0].id) : "nuevo");
  const [nuevo, setNuevo] = useState("");
  const [relacion, setRelacion] = useState("sin_evaluar");
  return (
    <Modal titulo="Vincular con un punto de evidencia" onCerrar={onCerrar} ancho="max-w-xl">
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        const r = await accion(async () => {
          let pid = Number(punto);
          if (punto === "nuevo") pid = (await api.post(`/evidencia/asuntos/${id}/puntos`, { descripcion: nuevo })).id;
          await api.post(`/evidencia/puntos/${pid}/vinculos`, { hecho_id: h.id, relacion });
        }, "Hecho vinculado a la matriz.");
        if (r) onCerrar();
      }}>
        <p className="rounded-lg bg-crema/70 p-3 text-sm">{h.fecha && <b className="text-marino">{fecha(h.fecha)} · </b>}{h.descripcion}</p>
        <div className="max-h-64 space-y-1.5 overflow-auto">
          {p.puntos.map((pt: any) => (
            <label key={pt.id} className={`flex cursor-pointer gap-2 rounded-xl border p-2.5 text-sm ${punto === String(pt.id) ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
              <input type="radio" name="punto" checked={punto === String(pt.id)} onChange={() => setPunto(String(pt.id))} />
              <span>{pt.descripcion} <span className="text-xs text-slate-500">· {pt.vinculos.length} fuente(s)</span>
                {pt.vinculos.some((v: any) => v.hecho_id === h.id) && <span className="text-xs font-semibold text-amber-700"> · ya vinculado</span>}</span>
            </label>))}
          <label className={`flex cursor-pointer gap-2 rounded-xl border p-2.5 text-sm ${punto === "nuevo" ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
            <input type="radio" name="punto" checked={punto === "nuevo"} onChange={() => setPunto("nuevo")} /><span>Nuevo punto…</span>
          </label>
          {punto === "nuevo" && <input className="campo" required minLength={3} maxLength={2000} autoFocus value={nuevo} onChange={(e) => setNuevo(e.target.value)} placeholder="Hecho que se busca acreditar" />}
        </div>
        <label className="block"><span className="etiqueta">Este hecho…</span>
          <select className="campo" value={relacion} onChange={(e) => setRelacion(e.target.value)}>
            {Object.entries(p.catalogos.relaciones).map(([k, t]: any) => <option key={k} value={k}>{k === "sin_evaluar" ? "Evaluar después" : t}</option>)}
          </select></label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Vincular</button></div>
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
