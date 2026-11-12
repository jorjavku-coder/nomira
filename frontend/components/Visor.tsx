"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha, mxn } from "@/lib/api";

const DPI = 130;

/** Comprobante original en su página, con la fila resaltada, y acciones de revisión. */
export default function Visor({ reciboId, filaId, resultado, editable, onCerrar, onCambio }: {
  reciboId: number; filaId?: number | null; resultado: any; editable: boolean; onCerrar: () => void; onCambio: () => void;
}) {
  const [recibo, setRecibo] = useState<any>(null);
  const [img, setImg] = useState<{ url: string; anchoPt: number; altoPt: number } | null>(null);
  const [sel, setSel] = useState<number | null>(filaId ?? null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [f, setF] = useState({ clave: "", concepto: "", importe: "", motivo: "" });
  const [motivoRecibo, setMotivoRecibo] = useState("");
  const [per, setPer] = useState({ periodo_inicio: "", periodo_fin: "", plaza: "" });
  const [nueva, setNueva] = useState({ clave: "", concepto: "", importe: "" });

  const estados = useMemo(() => {
    const m: Record<number, { t: string; clase: string; motivo?: string }> = {};
    for (const x of resultado.incluidos) m[x.fila_id] = { t: "Incluida", clase: "bg-emerald-100 text-emerald-800" };
    for (const x of resultado.excluidos) m[x.fila_id] = { t: "Excluida", clase: "bg-slate-200 text-slate-700", motivo: x.motivo };
    for (const x of resultado.pendientes) m[x.fila_id] = { t: "Pendiente", clase: "bg-amber-100 text-amber-800", motivo: x.motivo };
    return m;
  }, [resultado]);

  const aplicar = useCallback((r: any) => {
    setRecibo(r);
    setPer({ periodo_inicio: r.periodo_inicio || "", periodo_fin: r.periodo_fin || "", plaza: r.plaza || "" });
  }, []);
  useEffect(() => {
    let url = "";
    api.get(`/recibos/${reciboId}`).then(async (r) => {
      aplicar(r);
      const { blob } = await api.blob(`/documentos/${r.documento_id}/paginas/${r.pagina}/imagen?dpi=${DPI}`);
      url = URL.createObjectURL(blob);
      const i = new Image();
      i.onload = () => setImg({ url, anchoPt: (i.naturalWidth * 72) / DPI, altoPt: (i.naturalHeight * 72) / DPI });
      i.src = url;
    }).catch((e) => setError(e.message));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [reciboId, aplicar]);

  const fila = recibo?.filas.find((x: any) => x.id === sel);
  useEffect(() => {
    if (fila) setF({ clave: fila.clave || "", concepto: fila.concepto || "", importe: fila.importe || "", motivo: "" });
  }, [fila?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function accion(fn: () => Promise<any>, mensaje: string) {
    setError(""); setOk("");
    try { aplicar(await fn()); setOk(mensaje); onCambio(); } catch (e: any) { setError(e.message); }
  }
  const corregir = () => {
    const cuerpo: any = { motivo: f.motivo };
    if (f.clave !== (fila.clave || "")) cuerpo.clave = f.clave;
    if (f.concepto !== (fila.concepto || "")) cuerpo.concepto = f.concepto;
    if (f.importe !== (fila.importe || "")) cuerpo.importe = f.importe;
    return accion(() => api.post(`/filas/${fila.id}/corregir`, cuerpo), "Corrección registrada.");
  };
  const infoRecibo = resultado.recibos?.[String(reciboId)];
  const alertasRecibo = resultado.alertas.filter((a: any) => a.recibo_id === reciboId && !a.fila_id);

  const tabla = (tipo: string, titulo: string) => (
    <div>
      <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">{titulo}</h4>
      <table className="tabla">
        <tbody>
          {recibo.filas.filter((x: any) => x.tipo === tipo).map((x: any) => (
            <tr key={x.id} onClick={() => setSel(x.id)} className={`cursor-pointer ${sel === x.id ? "bg-turquesa-50" : "hover:bg-marino-50/50"}`}>
              <td className="w-14 font-mono font-semibold">{x.clave || "¿?"}</td>
              <td className="text-xs">{x.concepto || <i className="text-slate-400">(sin concepto)</i>}{x.corregida && <span className="ml-1 rounded bg-marino-50 px-1 text-[10px] font-semibold text-marino">corregida</span>}</td>
              <td className="num whitespace-nowrap">{x.importe === null ? <span className="font-sans text-amber-700">ilegible</span> : mxn(x.importe)}</td>
              <td className="w-20">{tipo === "percepcion" && estados[x.id]
                ? <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${estados[x.id].clase}`}>{estados[x.id].t}</span>
                : tipo === "deduccion" ? <span className="text-[11px] text-slate-400">no se suma</span> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <Modal titulo={recibo ? `Comprobante original — ${recibo.documento}, página ${recibo.pagina}` : "Comprobante original"} onCerrar={onCerrar} ancho="max-w-7xl">
      {!recibo ? <><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="max-h-[80vh] overflow-auto rounded border border-crema-300 bg-slate-100">
            {img ? (
              <div className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img.url} alt={`Página ${recibo.pagina} del comprobante`} className="block w-full" />
                {recibo.filas.filter((x: any) => x.bbox).map((x: any) => (
                  <button key={x.id} onClick={() => setSel(x.id)} title={`${x.clave || "¿?"} · ${x.importe ?? "ilegible"}`}
                    aria-label={`Fila ${x.clave || "sin clave"}`}
                    className={`absolute rounded-sm border ${sel === x.id ? "border-turquesa bg-turquesa/25 ring-2 ring-turquesa" : "border-transparent hover:bg-marino/10"}`}
                    style={{ left: `${((x.bbox[0] - 3) / img.anchoPt) * 100}%`, top: `${((x.bbox[1] - 2) / img.altoPt) * 100}%`,
                      width: `${((x.bbox[2] - x.bbox[0] + 6) / img.anchoPt) * 100}%`, height: `${((x.bbox[3] - x.bbox[1] + 4) / img.altoPt) * 100}%` }} />
                ))}
              </div>
            ) : <p className="p-4 text-sm text-slate-500">Cargando imagen…</p>}
          </div>
          <div className="max-h-[80vh] space-y-4 overflow-auto pr-1">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <div><span className="text-slate-500">Periodo:</span> <b>{recibo.periodo_inicio ? `${fecha(recibo.periodo_inicio)} – ${fecha(recibo.periodo_fin)}` : "no leído"}</b></div>
              <div><span className="text-slate-500">Núm. de recibo:</span> {recibo.num_recibo || "—"}</div>
              <div><span className="text-slate-500">Trabajador:</span> {recibo.trabajador_nombre || "no leído"}</div>
              <div><span className="text-slate-500">Plaza:</span> {recibo.plaza || "—"}</div>
              <div><span className="text-slate-500">Total percepciones (recibo):</span> {mxn(recibo.total_percepciones)}</div>
              <div><span className="text-slate-500">Estado del recibo:</span> <b>{infoRecibo?.estado || "—"}</b>{recibo.decision && ` (decisión: ${recibo.decision})`}</div>
            </div>
            {infoRecibo?.motivo && <Aviso tipo="alerta">{infoRecibo.motivo}</Aviso>}
            {alertasRecibo.map((a: any, i: number) => <Aviso key={i} tipo="alerta">{a.mensaje}</Aviso>)}
            <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
            {tabla("percepcion", "Percepciones (se evalúan contra el catálogo)")}
            {tabla("deduccion", "Deducciones (nunca se suman)")}

            {fila && (
              <div className="rounded-xl border border-turquesa bg-turquesa-50 p-3">
                <h4 className="font-semibold text-marino">Fila seleccionada: {fila.clave || "¿?"}</h4>
                <p className="text-xs text-slate-600">Lectura original: clave «{fila.clave_leida ?? "—"}» · concepto «{fila.concepto_leido ?? "—"}» · importe «{fila.importe_leido_texto ?? "—"}»
                  {fila.confianza !== null && ` · confianza OCR ${fila.confianza}`}{fila.origen === "manual" && " · fila agregada manualmente"}</p>
                {estados[fila.id]?.motivo && <p className="mt-1 text-xs font-semibold text-amber-800">{estados[fila.id].t}: {estados[fila.id].motivo}</p>}
                {editable && (
                  <div className="mt-2 space-y-2">
                    <div className="grid grid-cols-[6rem_1fr_8rem] gap-2">
                      <label><span className="etiqueta">Clave</span><input className="campo font-mono" value={f.clave} onChange={(e) => setF({ ...f, clave: e.target.value })} /></label>
                      <label><span className="etiqueta">Concepto</span><input className="campo" value={f.concepto} onChange={(e) => setF({ ...f, concepto: e.target.value })} /></label>
                      <label><span className="etiqueta">Importe</span><input className="campo text-right font-mono" inputMode="decimal" placeholder="0.00" value={f.importe} onChange={(e) => setF({ ...f, importe: e.target.value })} /></label>
                    </div>
                    <label className="block"><span className="etiqueta">Motivo (obligatorio)</span>
                      <input className="campo" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} placeholder="p. ej. Importe verificado en el original" /></label>
                    <div className="flex flex-wrap gap-2">
                      <button className="btn-primario" disabled={f.motivo.trim().length < 3} onClick={corregir}>Guardar corrección</button>
                      <button className="btn-sec" disabled={f.motivo.trim().length < 3 || fila.importe === null}
                        onClick={() => accion(() => api.post(`/filas/${fila.id}/confirmar`, { motivo: f.motivo }), "Lectura confirmada.")}>Confirmar lectura tal cual</button>
                    </div>
                    <p className="text-xs text-slate-500">Corregir una lectura no modifica el catálogo: si la clave no está autorizada, la fila queda excluida.</p>
                  </div>
                )}
              </div>
            )}

            {editable && (
              <details className="rounded-xl border border-crema-300 p-3" open={alertasRecibo.length > 0 || infoRecibo?.estado !== "incluido"}>
                <summary className="cursor-pointer font-semibold text-marino">Acciones sobre el recibo</summary>
                <div className="mt-3 space-y-3">
                  <label className="block"><span className="etiqueta">Motivo (obligatorio)</span>
                    <input className="campo" value={motivoRecibo} onChange={(e) => setMotivoRecibo(e.target.value)} /></label>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn-turquesa" disabled={motivoRecibo.trim().length < 3} onClick={() => accion(() => api.post(`/recibos/${reciboId}/decision`, { decision: "incluir", motivo: motivoRecibo }), "Recibo incluido por decisión del revisor.")}>Incluir este recibo</button>
                    <button className="btn-peligro" disabled={motivoRecibo.trim().length < 3} onClick={() => accion(() => api.post(`/recibos/${reciboId}/decision`, { decision: "excluir", motivo: motivoRecibo }), "Recibo excluido.")}>Excluir este recibo</button>
                    {recibo.decision && <button className="btn-sec" disabled={motivoRecibo.trim().length < 3} onClick={() => accion(() => api.post(`/recibos/${reciboId}/decision`, { decision: null, motivo: motivoRecibo }), "Decisión revertida.")}>Revertir decisión</button>}
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <label><span className="etiqueta">Periodo: inicio</span><input type="date" className="campo" value={per.periodo_inicio} onChange={(e) => setPer({ ...per, periodo_inicio: e.target.value })} /></label>
                    <label><span className="etiqueta">Periodo: fin</span><input type="date" className="campo" value={per.periodo_fin} onChange={(e) => setPer({ ...per, periodo_fin: e.target.value })} /></label>
                    <label><span className="etiqueta">Plaza</span><input className="campo" value={per.plaza} onChange={(e) => setPer({ ...per, plaza: e.target.value })} /></label>
                  </div>
                  <button className="btn-sec" disabled={motivoRecibo.trim().length < 3} onClick={() => accion(() => api.post(`/recibos/${reciboId}/corregir`, {
                    motivo: motivoRecibo, periodo_inicio: per.periodo_inicio || null, periodo_fin: per.periodo_fin || null, plaza: per.plaza || null }), "Datos del recibo corregidos.")}>Corregir periodo o plaza</button>
                  <div className="border-t border-crema-300 pt-3">
                    <span className="etiqueta">Agregar una percepción que no se detectó</span>
                    <div className="grid grid-cols-[6rem_1fr_8rem_auto] gap-2">
                      <input className="campo font-mono" placeholder="Clave" value={nueva.clave} onChange={(e) => setNueva({ ...nueva, clave: e.target.value })} />
                      <input className="campo" placeholder="Concepto" value={nueva.concepto} onChange={(e) => setNueva({ ...nueva, concepto: e.target.value })} />
                      <input className="campo text-right font-mono" placeholder="0.00" value={nueva.importe} onChange={(e) => setNueva({ ...nueva, importe: e.target.value })} />
                      <button className="btn-sec" disabled={motivoRecibo.trim().length < 3 || !nueva.clave || !nueva.importe}
                        onClick={() => accion(() => api.post(`/recibos/${reciboId}/filas`, { ...nueva, tipo: "percepcion", motivo: motivoRecibo }), "Fila agregada.").then(() => setNueva({ clave: "", concepto: "", importe: "" }))}>Agregar</button>
                    </div>
                  </div>
                </div>
              </details>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
