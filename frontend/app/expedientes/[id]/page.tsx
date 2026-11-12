"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import Visor from "@/components/Visor";
import { Aviso, Chip, Modal } from "@/components/ui";
import { api, fecha, fechaHora, mxn } from "@/lib/api";

type Pestana = "revision" | "documentos" | "resultados" | "trazabilidad";

export default function Expediente() {
  const { id } = useParams<{ id: string }>();
  const sesion = useSesion();
  const editor = !!sesion && sesion.usuario.rol !== "consulta";
  const [exp, setExp] = useState<any>(null);
  const [res, setRes] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [pestana, setPestana] = useState<Pestana>("revision");
  const [qSel, setQSel] = useState<string | null>(null);
  const [visor, setVisor] = useState<{ recibo: number; fila?: number | null } | null>(null);
  const [validar, setValidar] = useState(false);
  const [subida, setSubida] = useState<any[] | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const archivo = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async () => {
    try {
      const [e, r, d] = await Promise.all([api.get(`/expedientes/${id}`), api.get(`/expedientes/${id}/resultado`), api.get(`/expedientes/${id}/documentos`)]);
      setExp(e); setRes(r); setDocs(d);
      setQSel((q) => q ?? r.quincenas.find((x: any) => x.provisional)?.quincena ?? r.quincenas[0]?.quincena ?? null);
    } catch (e: any) { setError(e.message); }
  }, [id]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (exp?.estado !== "procesando") return;
    const t = setInterval(cargar, 2000);
    return () => clearInterval(t);
  }, [exp?.estado, cargar]);

  async function accion(fn: () => Promise<any>, mensaje = "") {
    setError(""); setOk("");
    try { await fn(); if (mensaje) setOk(mensaje); } catch (e: any) { setError(e.message); }
    await cargar();
  }
  async function subir(lista: FileList | null) {
    if (!lista?.length) return;
    const fd = new FormData();
    Array.from(lista).forEach((a) => fd.append("archivos", a));
    setSubiendo(true); setError("");
    try { setSubida(await api.subir(`/expedientes/${id}/documentos`, fd)); } catch (e: any) { setError(e.message); }
    setSubiendo(false);
    if (archivo.current) archivo.current.value = "";
    cargar();
  }

  if (!exp || !res) return <Shell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</Shell>;
  const validado = exp.estado === "validado";
  const editable = editor && !validado;
  const bloqueantes = res.alertas.filter((a: any) => a.bloqueante);
  const avisos = res.alertas.filter((a: any) => !a.bloqueante);
  const q = res.quincenas.find((x: any) => x.quincena === qSel);
  const de = (lista: any[]) => lista.filter((x) => x.quincena === qSel);
  const sinQuincena = { excluidos: res.excluidos.filter((x: any) => !x.quincena), pendientes: res.pendientes.filter((x: any) => !x.quincena) };
  const varias = res.plazas.length > 1;

  const filaAcciones = (x: any) => (
    <button className="btn-sec whitespace-nowrap" onClick={() => setVisor({ recibo: x.recibo_id, fila: x.fila_id })}>{editable ? "Revisar" : "Ver original"}</button>
  );

  return (
    <Shell>
      <Link href="/" className="text-sm text-turquesa-700 hover:underline">← Expedientes</Link>
      <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-extrabold text-marino">Expediente #{exp.id} · {exp.trabajador_nombre}</h1>
            <Chip estado={exp.estado} />
            {!validado && <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">Resultado provisional</span>}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            Periodo {fecha(exp.periodo_inicio)} – {fecha(exp.periodo_fin)} · {exp.quincenas_esperadas} quincenas esperadas
            {exp.identificador_laboral && <> · Id. laboral {exp.identificador_laboral}</>} · Catálogo «{res.catalogo.nombre}» versión {res.catalogo.version}
          </p>
          {validado && <p className="text-sm text-emerald-700">Validado por {res.estado_validacion.por} el {fechaHora(res.estado_validacion.fecha)}.</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => api.descargar(`/expedientes/${id}/exportar/excel`, `expediente-${id}.xlsx`).catch((e) => setError(e.message))}>Exportar Excel</button>
          <button className="btn-sec" onClick={() => api.descargar(`/expedientes/${id}/exportar/pdf`, `expediente-${id}.pdf`).catch((e) => setError(e.message))}>Exportar PDF</button>
          {editable && <button className="btn-turquesa" disabled={!res.puede_validarse} title={res.puede_validarse ? "" : "Resuelva los pendientes para poder validar"} onClick={() => setValidar(true)}>Validar resultado</button>}
          {editor && validado && <button className="btn-sec" onClick={() => { const m = prompt("Motivo para reabrir el expediente (la validación se revoca):"); if (m && m.trim().length >= 3) accion(() => api.post(`/expedientes/${id}/reabrir`, { motivo: m }), "Expediente reabierto."); }}>Reabrir</button>}
        </div>
      </div>

      <div className="my-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <div className="tarjeta p-5 md:col-span-2"><div className="etiqueta">Total del expediente {!validado && "(provisional)"}</div>
          <div className="font-marca text-2xl font-extrabold text-marino">{res.consolidado ? `${mxn(res.total_expediente)} MXN` : "Por plaza (sin consolidar)"}</div>
          {varias && <div className="mt-1 text-xs text-slate-600">{res.plazas.map((p: any) => `Plaza ${p.plaza}: ${mxn(p.total)}`).join(" · ")}</div>}</div>
        <div className="tarjeta p-5"><div className="etiqueta">Quincenas con comprobante</div><div className="font-marca text-2xl font-extrabold text-marino">{res.resumen.quincenas_con_recibo}<span className="text-base font-normal text-slate-500"> / {res.resumen.quincenas_esperadas}</span></div></div>
        <div className={`tarjeta p-5 ${res.resumen.quincenas_faltantes ? "border-red-200 bg-red-50" : ""}`}><div className="etiqueta">Quincenas faltantes</div><div className="font-marca text-2xl font-extrabold text-marino">{res.resumen.quincenas_faltantes}</div>
          <div className="text-xs text-slate-500">{res.resumen.quincenas_en_cero} con $0.00 autorizado</div></div>
        <div className={`tarjeta p-5 ${bloqueantes.length ? "border-amber-300 bg-amber-50" : ""}`}><div className="etiqueta">Pendientes por resolver</div><div className="font-marca text-2xl font-extrabold text-marino">{validado ? 0 : bloqueantes.length}</div></div>
      </div>

      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {editable && res.periodo_detectado && (res.periodo_detectado.inicio < exp.periodo_inicio || res.periodo_detectado.fin > exp.periodo_fin) && (
        <div className="mt-2"><Aviso tipo="alerta">
          Los recibos cargados cubren del <b>{fecha(res.periodo_detectado.inicio)}</b> al <b>{fecha(res.periodo_detectado.fin)}</b>, más de lo que abarca el periodo del expediente. Los que quedan fuera no se suman.{" "}
          <button className="font-semibold underline" onClick={() => accion(() => api.patch(`/expedientes/${id}`, {
            periodo_inicio: res.periodo_detectado.inicio < exp.periodo_inicio ? res.periodo_detectado.inicio : exp.periodo_inicio,
            periodo_fin: res.periodo_detectado.fin > exp.periodo_fin ? res.periodo_detectado.fin : exp.periodo_fin,
            quincenas_esperadas: null }), "Periodo ampliado a los recibos detectados.")}>Ampliar el periodo para incluirlos</button>
        </Aviso></div>
      )}
      {exp.estado === "procesando" && <Aviso tipo="info">Procesando documentos… esta página se actualiza sola.</Aviso>}

      <div className="mb-4 mt-4 flex gap-1 border-b border-crema-300" role="tablist">
        {([["revision", `Revisión${!validado && bloqueantes.length ? ` (${bloqueantes.length})` : ""}`], ["documentos", `Documentos (${docs.length})`], ["resultados", "Resultados"], ["trazabilidad", `Trazabilidad (${res.trazabilidad.correcciones.length})`]] as [Pestana, string][]).map(([k, t]) => (
          <button key={k} role="tab" aria-selected={pestana === k} onClick={() => setPestana(k)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-semibold ${pestana === k ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>{t}</button>
        ))}
      </div>

      {pestana === "revision" && (
        <div className="space-y-4">
          {!validado && bloqueantes.length > 0 && (
            <section className="tarjeta border-amber-300">
              <h2 className="border-b border-amber-200 bg-amber-50 px-4 py-2 font-semibold text-amber-900">Pendientes que impiden validar ({bloqueantes.length})</h2>
              <ul className="divide-y divide-slate-100">
                {bloqueantes.map((a: any, i: number) => (
                  <li key={i} className="flex items-center justify-between gap-4 px-4 py-2.5 text-sm">
                    <span>{a.quincena && <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{a.quincena}</span>}{a.mensaje}</span>
                    <span className="flex shrink-0 gap-2">
                      {a.recibo_id && <button className="btn-sec" onClick={() => setVisor({ recibo: a.recibo_id, fila: a.fila_id })}>{editable ? "Revisar" : "Ver original"}</button>}
                      {a.tipo === "plazas" && editable && (<>
                        <button className="btn-sec" onClick={() => accion(() => api.patch(`/expedientes/${id}`, { decision_plazas: "consolidar" }), "Plazas consolidadas.")}>Consolidar plazas</button>
                        <button className="btn-sec" onClick={() => accion(() => api.patch(`/expedientes/${id}`, { decision_plazas: "separar" }), "Plazas separadas.")}>Mantener separadas</button></>)}
                      {a.tipo === "pagina_sin_clasificar" && editable && <button className="btn-sec" onClick={() => { const m = prompt("Motivo para marcar la página como informativa:"); if (m && m.trim().length >= 3) accion(() => api.post(`/documentos/${a.documento_id}/paginas/${a.pagina}/clasificar`, { tipo: "informativa", motivo: m })); }}>Marcar como informativa</button>}
                      {(a.tipo === "documento_error" || a.tipo === "documento_en_proceso") && <button className="btn-sec" onClick={() => setPestana("documentos")}>Ir a documentos</button>}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {avisos.length > 0 && <details className="tarjeta px-4 py-2 text-sm"><summary className="cursor-pointer font-semibold text-marino">Avisos informativos ({avisos.length})</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">{avisos.map((a: any, i: number) => <li key={i}>{a.mensaje}
              {a.recibo_id && <button className="ml-2 text-turquesa-700 underline" onClick={() => setVisor({ recibo: a.recibo_id })}>ver recibo</button>}</li>)}</ul></details>}
          {exp.decision_plazas && varias && editable && <p className="text-sm text-slate-600">Plazas: <b>{exp.decision_plazas === "consolidar" ? "consolidadas" : "separadas"}</b>. <button className="text-turquesa-700 underline" onClick={() => accion(() => api.patch(`/expedientes/${id}`, { decision_plazas: exp.decision_plazas === "consolidar" ? "separar" : "consolidar" }))}>Cambiar</button></p>}

          <div className="grid gap-4 lg:grid-cols-[19rem_minmax(0,1fr)]">
            <nav className="tarjeta max-h-[70vh] overflow-auto" aria-label="Quincenas">
              <h2 className="sticky top-0 border-b border-crema-300 bg-white px-3 py-2 text-sm font-semibold text-marino">Quincenas ({res.quincenas.length})</h2>
              {res.quincenas.length === 0 && <p className="p-3 text-sm text-slate-500">El periodo no contiene quincenas completas.</p>}
              <ul>
                {res.quincenas.map((x: any) => (
                  <li key={x.quincena}>
                    <button onClick={() => setQSel(x.quincena)} aria-current={qSel === x.quincena}
                      className={`flex w-full items-center justify-between gap-2 border-b border-crema-200 px-3 py-2 text-left text-sm ${qSel === x.quincena ? "bg-turquesa-50" : "hover:bg-marino-50/50"}`}>
                      <span><span className="font-semibold text-marino">{x.numero}.</span> {x.etiqueta.replace(" quincena de ", " qna. ")}
                        <span className="block text-xs text-slate-500">{fecha(x.inicio)} – {fecha(x.fin)}</span></span>
                      <span className="text-right">
                        {x.estado === "faltante" ? <Chip estado="faltante" /> : x.estado === "pendiente" ? <Chip estado="pendiente" /> : <span className="text-sm font-semibold tabular-nums">{mxn(x.total)}</span>}
                        {x.provisional && x.estado !== "pendiente" && <span className="block text-[11px] font-semibold text-amber-700">con pendientes</span>}
                        {x.estado === "cero" && <span className="block text-[11px] text-slate-500">sin autorizadas</span>}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </nav>

            <div className="min-w-0 space-y-4">
              {q && (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-lg font-semibold text-marino">Quincena {q.numero} — {q.etiqueta} <span className="text-sm font-normal text-slate-500">({fecha(q.inicio)} al {fecha(q.fin)})</span></h2>
                    <div className="flex gap-2">{q.recibos.map((r: number, i: number) => <button key={r} className="btn-sec" onClick={() => setVisor({ recibo: r })}>Ver comprobante{q.recibos.length > 1 ? ` ${i + 1}` : ""}</button>)}</div>
                  </div>
                  {q.estado === "faltante" && <Aviso>No hay comprobante para esta quincena. Se reporta como <b>faltante</b>; no se le asigna ningún importe.</Aviso>}
                  {q.estado === "cero" && <Aviso tipo="info">Hay comprobante, pero ninguna de sus claves está autorizada: total <b>$0.00</b> (no es una quincena faltante).</Aviso>}
                  <section className="tarjeta overflow-x-auto">
                    <h3 className="border-b border-crema-300 px-4 py-2 font-semibold text-emerald-800">Conceptos incluidos ({de(res.incluidos).length})</h3>
                    <table className="tabla">
                      <thead><tr><th>Clave</th><th>Concepto en el recibo</th><th>Concepto del catálogo</th>{varias && <th>Plaza</th>}<th className="num">Importe</th><th></th></tr></thead>
                      <tbody>
                        {de(res.incluidos).length === 0 && <tr><td colSpan={6} className="text-slate-500">Ninguno.</td></tr>}
                        {de(res.incluidos).map((x: any) => (
                          <tr key={x.fila_id}><td className="font-mono font-semibold">{x.clave}</td><td>{x.concepto_original || <i className="text-slate-400">(sin concepto)</i>}
                            {x.retroactivo && <span className="ml-1 rounded bg-marino-50 px-1 text-[10px] font-semibold text-marino" title={res.politica_retroactivos}>retroactivo</span>}
                            {x.corregida && <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-800">corregida</span>}</td>
                            <td className="text-slate-600">{x.concepto_catalogo}</td>{varias && <td className="font-mono text-xs">{x.plaza}</td>}
                            <td className={`num ${x.negativo ? "text-red-700" : ""}`}>{mxn(x.importe)}</td><td className="text-right">{filaAcciones(x)}</td></tr>
                        ))}
                      </tbody>
                      {q.estado !== "faltante" && <tfoot>{varias && q.plazas.map((pz: any) => <tr key={pz.plaza} className="bg-slate-50 font-semibold"><td colSpan={4}>Subtotal plaza {pz.plaza}</td><td className="num">{mxn(pz.total)}</td><td></td></tr>)}<tr className="bg-turquesa-50 font-bold"><td colSpan={varias ? 4 : 3}>TOTAL de la quincena{varias && (res.consolidado ? " (plazas consolidadas)" : " (suma de plazas, sin consolidar)")}{q.provisional && " (provisional)"}</td><td className="num">{mxn(q.total)}</td><td></td></tr></tfoot>}
                    </table>
                  </section>
                  {de(res.pendientes).length > 0 && (
                    <section className="tarjeta overflow-x-auto border-amber-300">
                      <h3 className="border-b border-amber-200 bg-amber-50 px-4 py-2 font-semibold text-amber-900">Pendientes de revisión ({de(res.pendientes).length}) — no se suman hasta resolverse</h3>
                      <table className="tabla"><thead><tr><th>Clave</th><th>Concepto en el recibo</th><th className="num">Importe leído</th><th>Motivo</th><th></th></tr></thead>
                        <tbody>{de(res.pendientes).map((x: any) => (<tr key={x.fila_id}><td className="font-mono font-semibold">{x.clave || "¿?"}</td><td>{x.concepto_original}</td>
                          <td className="num">{x.importe === null ? <span className="font-sans text-amber-700">ilegible</span> : mxn(x.importe)}</td><td>{x.motivo}</td><td className="text-right">{filaAcciones(x)}</td></tr>))}</tbody></table>
                    </section>
                  )}
                  <section className="tarjeta overflow-x-auto">
                    <h3 className="border-b border-crema-300 px-4 py-2 font-semibold text-slate-700">Conceptos excluidos ({de(res.excluidos).length})</h3>
                    <table className="tabla"><thead><tr><th>Clave</th><th>Concepto en el recibo</th><th className="num">Importe</th><th>Motivo de exclusión</th><th></th></tr></thead>
                      <tbody>{de(res.excluidos).length === 0 && <tr><td colSpan={5} className="text-slate-500">Ninguno.</td></tr>}
                        {de(res.excluidos).map((x: any) => (<tr key={x.fila_id} className="text-slate-600"><td className="font-mono font-semibold">{x.clave}</td><td>{x.concepto_original || <i className="text-slate-400">(sin concepto)</i>}</td>
                          <td className="num">{mxn(x.importe)}</td><td>{x.motivo}</td><td className="text-right">{filaAcciones(x)}</td></tr>))}</tbody></table>
                  </section>
                </>
              )}
              {(sinQuincena.pendientes.length > 0 || sinQuincena.excluidos.length > 0) && (
                <section className="tarjeta overflow-x-auto">
                  <h3 className="border-b border-crema-300 px-4 py-2 font-semibold text-slate-700">Filas de recibos sin quincena asignada ({sinQuincena.pendientes.length + sinQuincena.excluidos.length})</h3>
                  <table className="tabla"><tbody>{[...sinQuincena.pendientes, ...sinQuincena.excluidos].map((x: any) => (<tr key={x.fila_id}><td className="font-mono font-semibold">{x.clave || "¿?"}</td><td>{x.concepto_original}</td><td className="num">{mxn(x.importe)}</td><td>{x.motivo}</td><td className="text-right">{filaAcciones(x)}</td></tr>))}</tbody></table>
                </section>
              )}
            </div>
          </div>
        </div>
      )}

      {pestana === "documentos" && (
        <div className="space-y-4">
          {editable && (
            <div className="tarjeta flex flex-wrap items-center gap-3 border-dashed p-4"
              onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); subir(e.dataTransfer.files); }}>
              <input ref={archivo} type="file" accept="application/pdf,.pdf" multiple className="hidden" id="archivos" onChange={(e) => subir(e.target.files)} />
              <button className="btn-turquesa" disabled={subiendo} onClick={() => archivo.current?.click()}>{subiendo ? "Subiendo…" : "Subir comprobantes PDF"}</button>
              <span className="text-sm text-slate-500">o arrástrelos aquí. PDF con texto o escaneados (OCR). Un PDF puede traer muchos recibos y páginas informativas.</span>
            </div>
          )}
          {validado && editor && <Aviso tipo="info">El expediente está validado. Reábralo para cargar o modificar documentos.</Aviso>}
          {subida && <div className="space-y-1">{subida.map((s, i) => <Aviso key={i} tipo={s.aceptado ? "ok" : "alerta"}><b>{s.nombre}:</b> {s.aceptado ? "recibido; procesando." : s.motivo}</Aviso>)}</div>}
          <div className="tarjeta overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>Documento</th><th>Estado</th><th>Páginas</th><th>Recibos</th><th>Informativas</th><th>Con OCR</th><th>Huella SHA-256</th><th></th></tr></thead>
              <tbody>
                {docs.length === 0 && <tr><td colSpan={8} className="py-6 text-center text-slate-500">Aún no hay documentos.</td></tr>}
                {docs.map((d) => (
                  <tr key={d.id}>
                    <td>{d.nombre}<div className="text-xs text-slate-500">{(d.tamano_bytes / 1048576).toFixed(1)} MB · cargado {fechaHora(d.creado_en)}{d.intentos > 1 && ` · ${d.intentos} intentos`}</div>
                      {d.error && <div className="mt-1 text-xs text-red-700">{d.error}</div>}</td>
                    <td><Chip estado={d.estado} /></td><td>{d.paginas ?? "—"}</td><td>{d.paginas_recibo}</td><td>{d.paginas_informativas}{d.paginas_desconocidas > 0 && <span className="text-amber-700"> (+{d.paginas_desconocidas} sin clasificar)</span>}</td><td>{d.paginas_ocr}</td>
                    <td className="font-mono text-xs" title={d.sha256}>{d.sha256.slice(0, 12)}…</td>
                    <td className="whitespace-nowrap text-right">
                      <button className="btn-sec mr-1" onClick={() => api.descargar(`/documentos/${d.id}/archivo`, `documento-${d.id}.pdf`).catch((e) => setError(e.message))}>Descargar</button>
                      {editable && d.estado === "error" && <button className="btn-turquesa mr-1" onClick={() => accion(() => api.post(`/documentos/${d.id}/reintentar`, {}))}>Reintentar</button>}
                      {editable && d.estado === "procesado" && <button className="btn-sec mr-1" onClick={() => { if (confirm("Volver a leer el documento descarta las correcciones hechas sobre sus recibos (quedan en la bitácora). ¿Continuar?")) accion(() => api.post(`/documentos/${d.id}/reintentar`, { forzar: true })); }}>Reprocesar</button>}
                      {editable && d.estado !== "procesando" && <button className="btn-peligro" onClick={() => { if (confirm(`¿Eliminar «${d.nombre}» y sus recibos de este expediente?`)) accion(() => api.borrar(`/documentos/${d.id}`), "Documento eliminado."); }}>Eliminar</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {pestana === "resultados" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="tarjeta overflow-x-auto">
            <h2 className="border-b border-crema-300 px-4 py-2 font-semibold text-marino">Total por quincena</h2>
            <table className="tabla"><thead><tr><th>#</th><th>Quincena</th><th>Periodo</th><th>Estado</th><th className="num">Total</th></tr></thead>
              <tbody>{res.quincenas.map((x: any) => (<tr key={x.quincena}><td>{x.numero}</td><td>{x.etiqueta}</td><td className="whitespace-nowrap">{fecha(x.inicio)} – {fecha(x.fin)}</td>
                <td><Chip estado={x.estado} />{x.provisional && x.estado !== "pendiente" && <span className="ml-1 text-xs text-amber-700">provisional</span>}</td>
                <td className="num">{x.estado === "faltante" || x.estado === "pendiente" ? "—" : mxn(x.total)}</td></tr>))}</tbody>
              <tfoot><tr className="bg-turquesa-50 font-bold"><td colSpan={4}>TOTAL DEL EXPEDIENTE{!validado && " (provisional)"}</td><td className="num">{res.consolidado ? mxn(res.total_expediente) : "por plaza"}</td></tr></tfoot></table>
          </section>
          <div className="space-y-4">
            <section className="tarjeta overflow-x-auto">
              <h2 className="border-b border-crema-300 px-4 py-2 font-semibold text-marino">Total por clave de prestación</h2>
              <table className="tabla"><thead><tr><th>Clave</th><th>Concepto (catálogo)</th><th>Veces</th><th className="num">Total</th></tr></thead>
                <tbody>{res.acumulado_por_clave.length === 0 && <tr><td colSpan={4} className="text-slate-500">Sin conceptos incluidos.</td></tr>}
                  {res.acumulado_por_clave.map((a: any) => (<tr key={a.clave}><td className="font-mono font-semibold">{a.clave}</td><td>{a.concepto_catalogo}</td><td>{a.apariciones}</td><td className="num">{mxn(a.total)}</td></tr>))}</tbody></table>
            </section>
            <section className="tarjeta p-4 text-sm">
              <h2 className="mb-1 font-semibold text-marino">Quincenas faltantes ({res.faltantes.length})</h2>
              {res.faltantes.length === 0 ? <p className="text-slate-500">Ninguna.</p> : <ul className="list-disc pl-5">{res.faltantes.map((f: any) => <li key={f.quincena}>{f.etiqueta} ({fecha(f.inicio)} – {fecha(f.fin)})</li>)}</ul>}
              <h2 className="mb-1 mt-4 font-semibold text-marino">Política de retroactivos</h2><p className="text-slate-600">{res.politica_retroactivos}</p>
              <h2 className="mb-1 mt-4 font-semibold text-marino">Reglas aplicadas</h2>
              <p className="text-slate-600">Se suman solo percepciones cuya clave coincide exactamente con una clave activa del catálogo (versión {res.catalogo.version}, {res.catalogo.claves_activas} claves). Deducciones, total neto y totales del recibo nunca se suman.</p>
            </section>
          </div>
        </div>
      )}

      {pestana === "trazabilidad" && (
        <section className="tarjeta overflow-x-auto">
          <h2 className="border-b border-crema-300 px-4 py-2 font-semibold text-marino">Correcciones y decisiones registradas</h2>
          <table className="tabla"><thead><tr><th>Fecha</th><th>Usuario</th><th>Elemento</th><th>Campo</th><th>Valor anterior</th><th>Valor nuevo</th><th>Motivo</th></tr></thead>
            <tbody>{res.trazabilidad.correcciones.length === 0 && <tr><td colSpan={7} className="py-6 text-center text-slate-500">Sin correcciones.</td></tr>}
              {res.trazabilidad.correcciones.map((c: any) => (<tr key={c.id}><td className="whitespace-nowrap">{fechaHora(c.fecha)}</td><td>{c.usuario}</td>
                <td className="text-xs">{c.referencia?.documento} p.{c.referencia?.pagina}{c.referencia?.clave_leida && ` · clave leída ${c.referencia.clave_leida}`}</td>
                <td>{c.campo}</td><td className="font-mono text-xs">{c.valor_anterior ?? "—"}</td><td className="font-mono text-xs">{c.valor_nuevo ?? "—"}</td><td>{c.motivo}</td></tr>))}</tbody></table>
        </section>
      )}

      {visor && <Visor reciboId={visor.recibo} filaId={visor.fila} resultado={res} editable={editable} onCerrar={() => setVisor(null)} onCambio={cargar} />}
      {validar && <DialogoValidar res={res} onCerrar={() => setValidar(false)} onValidado={() => { setValidar(false); setOk("Expediente validado. El resultado quedó congelado."); cargar(); }} id={id} />}
    </Shell>
  );
}

function DialogoValidar({ res, id, onCerrar, onValidado }: { res: any; id: string; onCerrar: () => void; onValidado: () => void }) {
  const [acepta, setAcepta] = useState(false);
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const n = res.faltantes.length;
  return (
    <Modal titulo="Validar resultado" onCerrar={onCerrar}>
      <div className="space-y-3 text-sm">
        <p>Al validar, el resultado y la versión del catálogo quedan congelados. Cualquier cambio posterior exige reabrir el expediente y queda en la bitácora.</p>
        <p className="text-lg font-bold text-marino">{res.consolidado ? `Total: ${mxn(res.total_expediente)} MXN` : res.plazas.map((p: any) => `Plaza ${p.plaza}: ${mxn(p.total)}`).join(" · ")}</p>
        {n > 0 && <label className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3"><input type="checkbox" className="mt-1" checked={acepta} onChange={(e) => setAcepta(e.target.checked)} />
          <span>Reconozco que faltan comprobantes de <b>{n}</b> quincena(s) y que no se les asigna ningún importe: {res.faltantes.slice(0, 6).map((f: any) => f.etiqueta).join("; ")}{n > 6 && "…"}</span></label>}
        <label className="block"><span className="etiqueta">Notas de validación (opcional)</span><textarea className="campo" rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={n > 0 && !acepta} onClick={() => api.post(`/expedientes/${id}/validar`, { acepta_faltantes: acepta, notas: notas || null }).then(onValidado).catch((e) => setError(e.message))}>Validar</button></div>
      </div>
    </Modal>
  );
}
