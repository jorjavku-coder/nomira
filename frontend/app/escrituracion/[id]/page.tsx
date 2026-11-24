"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { type ClienteBreve, SelectorCliente } from "@/components/clientes";
import { Barra, fechaCorta, fechaHoraCorta, Semaforo, SEMAFORO, useCatalogosEsc } from "@/components/escrituracion";
import { Aviso, Modal } from "@/components/ui";
import { api, hoyLocal, mxn } from "@/lib/api";

const ESTADO_HITO: Record<string, [string, string]> = {
  pendiente: ["Pendiente", "bg-slate-100 text-slate-600"], en_proceso: ["En proceso", "bg-sky-100 text-sky-800"], observado: ["Con observaciones", "bg-amber-100 text-amber-800"],
  hecho: ["Hecho", "bg-emerald-100 text-emerald-800"], no_aplica: ["No aplica", "bg-slate-100 text-slate-400"],
};
const ESTADO_REQ: Record<string, [string, string]> = {
  pendiente: ["Falta", "bg-red-100 text-red-700"], recibido: ["Por validar", "bg-amber-100 text-amber-800"], validado: ["Validado", "bg-emerald-100 text-emerald-800"],
  rechazado: ["Rechazado", "bg-red-100 text-red-700"], no_aplica: ["No aplica", "bg-slate-100 text-slate-400"],
};
const local = (iso?: string | null) => (iso ? new Date(new Date(iso).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "");

export default function Expediente() {
  const { id } = useParams<{ id: string }>();
  const cat = useCatalogosEsc();
  const [e, setE] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [dlg, setDlg] = useState<{ t: string; x?: any } | null>(null);
  const cargar = useCallback(() => api.get(`/escrituracion/expedientes/${id}`).then(setE).catch((x) => setError(x.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(f: () => Promise<any>, msj = "") {
    setError(""); setOk("");
    try { const r = await f(); if (r?.id) setE(r); else cargar(); if (msj) setOk(msj); setDlg(null); } catch (x: any) { setError(x.message); }
  }
  async function subir(r: any, archivo: File) {
    const d = new FormData(); d.append("archivo", archivo);
    await hacer(() => api.subir(`/escrituracion/requisitos/${r.id}/archivo`, d), "Documento guardado: márquelo como validado cuando lo revise.");
  }
  async function verArchivo(r: any) {
    try { const { blob } = await api.blob(`/escrituracion/requisitos/${r.id}/archivo`); window.open(URL.createObjectURL(blob), "_blank", "noopener"); } catch (x: any) { setError(x.message); }
  }
  if (!e || !cat) return <Shell><Aviso>{error}</Aviso></Shell>;
  const edita = cat.puede_editar;
  const s = e.semaforo;
  const grupos: Record<string, any[]> = {};
  for (const r of e.requisitos) (grupos[r.de] ||= []).push(r);
  return (
    <Shell>
      <Link href="/escrituracion" className="text-sm font-semibold text-turquesa-700">← Escrituración</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div><p className="font-mono text-xs text-slate-400">{e.folio} · {e.acto_texto}{e.estado !== "abierto" && ` · ${e.estado}`}</p>
          <h1 className="text-3xl font-extrabold text-marino">{e.titulo}</h1>
          {e.inmueble && <p className="text-sm text-slate-600">📍 {e.inmueble}</p>}
          <p className="text-xs text-slate-500">Responsable: {e.responsable || "—"}{e.valor_operacion && ` · Valor: ${mxn(e.valor_operacion)}`}</p></div>
        {edita && <div className="flex flex-wrap gap-2"><button className="btn-sec" onClick={() => setDlg({ t: "datos" })}>Editar datos y cita</button>
          {e.estado === "abierto" ? <><button className="btn-sec" onClick={() => hacer(() => api.post(`/escrituracion/expedientes/${id}/estado`, { estado: "concluido" }), "Expediente concluido.")}>Concluir</button>
            <button className="btn-sec text-red-700" onClick={() => hacer(() => api.post(`/escrituracion/expedientes/${id}/estado`, { estado: "cancelado" }), "Expediente cancelado: sus enlaces dejan de funcionar.")}>Cancelar</button></>
            : <button className="btn-sec" onClick={() => hacer(() => api.post(`/escrituracion/expedientes/${id}/estado`, { estado: "abierto" }), "Reabierto.")}>Reabrir</button>}</div>}
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      {/* Semáforo listo para firmar */}
      <section className={`mb-5 rounded-2xl border-2 p-4 ${SEMAFORO[s.color].caja}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><Semaforo s={s} /><p className="text-sm">{s.validados} de {s.total} documentos validados y vigentes al {s.con_cita ? `día de la firma (${fechaCorta(s.referencia)})` : "día de hoy"}.</p></div>
          <div className="text-right text-sm">{e.cita_firma ? <><b>✍️ Firma: {fechaHoraCorta(e.cita_firma)}</b>{e.cita_lugar && <p className="text-xs">{e.cita_lugar}</p>}</>
            : edita && <button className="btn-sec" onClick={() => setDlg({ t: "datos" })}>Agendar firma</button>}</div>
        </div>
        {(s.faltan.length > 0 || s.vencidos.length > 0 || s.por_validar.length > 0 || s.por_vencer.length > 0) && <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          {s.faltan.length > 0 && <Lista titulo="Faltan" items={s.faltan} />}
          {s.vencidos.length > 0 && <Lista titulo={s.con_cita ? "Vencen antes de la firma" : "Vencidos"} items={s.vencidos} fecha />}
          {s.por_validar.length > 0 && <Lista titulo="Recibidos, falta validarlos" items={s.por_validar} />}
          {s.por_vencer.length > 0 && <Lista titulo="Vencen pocos días después de la firma" items={s.por_vencer} fecha />}
        </div>}
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_23rem]">
        <div className="space-y-5">
          {/* Avance */}
          <section className="tarjeta p-4">
            <div className="mb-3 flex items-center gap-3"><h2 className="font-semibold text-marino">Avance del trámite</h2><div className="flex-1"><Barra pct={e.avance.porcentaje} /></div><span className="text-sm font-bold text-marino">{e.avance.porcentaje}%</span></div>
            <ol className="space-y-1">{e.hitos.map((h: any) => (
              <li key={h.id} className="flex flex-wrap items-center gap-2 rounded-xl px-2 py-2 hover:bg-crema/50">
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${h.estado === "hecho" ? "bg-emerald-500 text-white" : h.estado === "observado" ? "bg-amber-400 text-white" : "bg-crema-200 text-slate-500"}`}>{h.estado === "hecho" ? "✓" : h.orden}</span>
                <span className={`flex-1 text-sm ${h.estado === "no_aplica" ? "text-slate-400 line-through" : "font-semibold text-marino"}`}>{h.nombre}
                  {!h.visible_cliente && <span className="ml-2 text-xs font-normal text-slate-400">(interna)</span>}
                  {h.nota_publica && <span className="block text-xs font-normal text-slate-600">💬 {h.nota_publica}</span>}</span>
                <span className="text-xs text-slate-500">{h.fecha && fechaCorta(h.fecha)}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_HITO[h.estado][1]}`}>{ESTADO_HITO[h.estado][0]}</span>
                {edita && <span className="flex gap-1">{h.estado !== "hecho" && <button className="btn-sec px-2 py-1 text-xs" onClick={() => hacer(() => api.put(`/escrituracion/hitos/${h.id}`, { estado: "hecho", fecha: hoyLocal(), nota_publica: h.nota_publica, visible_cliente: h.visible_cliente }), `«${h.nombre}» marcado como hecho${h.visible_cliente ? "; avisamos a quienes siguen el trámite" : ""}.`)}>✓ Hecho</button>}
                  <button className="px-2 py-1 text-xs text-slate-500 underline" onClick={() => setDlg({ t: "hito", x: h })}>Editar</button></span>}
              </li>))}</ol>
          </section>

          {/* Documentos */}
          <section className="tarjeta p-4">
            <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-marino">Documentos para firmar</h2>
              {edita && <button className="text-sm font-semibold text-turquesa-700 underline" onClick={() => setDlg({ t: "nuevo_req" })}>+ Agregar documento</button>}</div>
            {Object.entries(grupos).map(([de, reqs]) => (
              <div key={de} className="mb-4"><h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">{de}</h3>
                <ul className="divide-y divide-crema-200 rounded-xl border border-crema-200">{reqs.map((r: any) => (
                  <li key={r.id} className={`flex flex-wrap items-center gap-2 px-3 py-2 text-sm ${r.estado === "no_aplica" ? "opacity-50" : ""}`}>
                    <div className="min-w-0 flex-1"><p className="font-semibold text-marino">{r.nombre}{!r.obligatorio && <span className="ml-1 text-xs font-normal text-slate-400">(opcional)</span>}</p>
                      <p className="text-xs text-slate-500">{r.vigencia_dias ? `Vigencia ${r.vigencia_dias} días` : "Sin vigencia"}{r.expedido_en && ` · expedido ${fechaCorta(r.expedido_en)}`}
                        {r.vence_en && <span className={r.vencido ? "font-semibold text-red-700" : ""}> · vence {fechaCorta(r.vence_en)}</span>}
                        {r.origen === "cliente" && <span className="font-semibold text-turquesa-700"> · lo subió el cliente</span>}{r.validado_por && ` · validó ${r.validado_por}`}</p>
                      {r.nota && <p className="text-xs text-slate-600">{r.estado === "rechazado" ? "Para corregir: " : ""}{r.nota}</p>}</div>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_REQ[r.estado][1]}`}>{ESTADO_REQ[r.estado][0]}</span>
                    {r.tiene_archivo && <button className="text-xs font-semibold text-turquesa-700 underline" onClick={() => verArchivo(r)}>Ver</button>}
                    {edita && <span className="flex flex-wrap gap-1">
                      <label className="cursor-pointer text-xs font-semibold text-slate-600 underline">Subir<input type="file" className="sr-only" accept="application/pdf,image/jpeg,image/png,image/webp" onChange={(ev) => ev.target.files?.[0] && subir(r, ev.target.files[0])} /></label>
                      {r.estado !== "validado" && r.estado !== "pendiente" && <button className="btn-sec px-2 py-0.5 text-xs" onClick={() => setDlg({ t: "validar", x: r })}>Validar</button>}
                      <button className="text-xs text-slate-500 underline" onClick={() => setDlg({ t: "req", x: r })}>Más</button></span>}
                  </li>))}</ul></div>))}
          </section>
        </div>

        <div className="space-y-5">
          <section className="tarjeta p-4 text-sm">
            <h2 className="mb-2 font-semibold text-marino">Datos de la escritura</h2>
            <dl className="space-y-1">{[["Escritura", e.numero_escritura && `${e.numero_escritura}${e.volumen ? ` · vol. ${e.volumen}` : ""}`], ["Folio real", e.folio_real], ["Clave catastral", e.clave_catastral],
              ["Entrada al Registro", e.folio_registro]].map(([k, v]) => <div key={k} className="grid grid-cols-[8rem_1fr] gap-2"><dt className="text-slate-500">{k}</dt><dd>{v || "—"}</dd></div>)}</dl>
            {e.mensaje_cliente && <p className="mt-2 rounded-lg bg-turquesa-50 p-2 text-xs"><b>Aviso que ve el cliente:</b> {e.mensaje_cliente}</p>}
            {e.notas && <p className="mt-2 whitespace-pre-line rounded-lg bg-crema/60 p-2 text-xs"><b>Notas internas:</b> {e.notas}</p>}
          </section>
          <section className="tarjeta p-4 text-sm">
            <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-marino">Partes</h2>
              {edita && <button className="text-sm font-semibold text-turquesa-700 underline" onClick={() => setDlg({ t: "parte" })}>+ Agregar</button>}</div>
            <ul className="divide-y divide-crema-200">{e.partes.map((p: any) => (
              <li key={p.id} className="flex items-start justify-between gap-2 py-2"><span><span className="text-xs text-slate-500">{p.rol_texto}</span><br />
                {p.cr_cliente_id ? <Link href={`/clientes/${p.cr_cliente_id}`} className="font-semibold text-marino hover:underline">{p.nombre}</Link> : <b className="text-marino">{p.nombre}</b>}
                <span className="block text-xs text-slate-500">{[p.email, p.telefono].filter(Boolean).join(" · ")}</span></span>
                {edita && <button className="text-xs text-slate-400 underline" onClick={() => hacer(() => api.borrar(`/escrituracion/partes/${p.id}`), "Parte quitada (con sus documentos).")}>Quitar</button>}</li>))}</ul>
          </section>
          <section className="tarjeta p-4 text-sm">
            <div className="mb-1 flex items-center justify-between"><h2 className="font-semibold text-marino">Seguimiento en línea</h2>
              {edita && e.estado !== "cancelado" && <button className="btn-turquesa px-3 py-1 text-xs" onClick={() => setDlg({ t: "enlace" })}>+ Compartir avance</button>}</div>
            <p className="mb-2 text-xs text-slate-500">Cada persona ve el avance y los documentos que le tocan (puede subirlos). Nunca ve notas internas, el valor ni datos de las otras partes.</p>
            {e.accesos.length ? <ul className="divide-y divide-crema-200">{e.accesos.map((a: any) => (
              <li key={a.id} className="flex items-start justify-between gap-2 py-2"><span><b className="text-marino">{a.nombre}</b> <span className="text-xs text-slate-500">({a.tipo === "parte" ? "parte" : a.tipo})</span>
                <span className="block text-xs text-slate-500">{a.estado === "activo" ? `Vigente hasta ${fechaCorta(a.expira_en)}` : a.estado} · {a.visitas} visita(s){a.ultimo_acceso && `, última ${fechaCorta(a.ultimo_acceso)}`}{a.avisar && a.email && " · recibe avisos"}</span></span>
                {edita && a.estado === "activo" && <button className="text-xs text-red-700 underline" onClick={() => hacer(() => api.post(`/escrituracion/accesos/${a.id}/revocar`), "Enlace desactivado.")}>Desactivar</button>}</li>))}</ul>
              : <p className="text-xs text-slate-500">Aún no se ha compartido con nadie.</p>}
          </section>
        </div>
      </div>

      {dlg?.t === "datos" && <Datos e={e} cat={cat} onCerrar={() => setDlg(null)} onGuardar={(d) => hacer(() => api.put(`/escrituracion/expedientes/${id}`, d), "Datos guardados.")} />}
      {dlg?.t === "hito" && <Hito h={dlg.x} onCerrar={() => setDlg(null)} onGuardar={(d) => hacer(() => api.put(`/escrituracion/hitos/${dlg.x.id}`, d), "Etapa actualizada.")} />}
      {dlg?.t === "validar" && <ReqEstado r={dlg.x} modo="validar" onCerrar={() => setDlg(null)} onGuardar={(d) => hacer(() => api.put(`/escrituracion/requisitos/${dlg.x.id}`, d), "Documento actualizado.")} />}
      {dlg?.t === "req" && <ReqEstado r={dlg.x} modo="mas" onCerrar={() => setDlg(null)} onGuardar={(d) => hacer(() => api.put(`/escrituracion/requisitos/${dlg.x.id}`, d), "Documento actualizado.")}
        onBorrar={() => hacer(() => api.borrar(`/escrituracion/requisitos/${dlg.x.id}`), "Documento quitado de la lista.")} />}
      {dlg?.t === "nuevo_req" && <NuevoReq e={e} onCerrar={() => setDlg(null)} onGuardar={(d) => hacer(() => api.post(`/escrituracion/expedientes/${id}/requisitos`, d), "Documento agregado.")} />}
      {dlg?.t === "parte" && <NuevaParte cat={cat} onCerrar={() => setDlg(null)} onGuardar={(d) => hacer(() => api.post(`/escrituracion/expedientes/${id}/partes`, d), "Parte agregada con su lista de documentos.")} />}
      {dlg?.t === "enlace" && <Compartir e={e} onCerrar={() => { setDlg(null); cargar(); }} />}
    </Shell>
  );
}

function Lista({ titulo, items, fecha }: { titulo: string; items: any[]; fecha?: boolean }) {
  return <div className="rounded-xl bg-white/70 p-3"><p className="mb-1 text-xs font-bold uppercase tracking-wide">{titulo} ({items.length})</p>
    <ul className="space-y-0.5 text-xs">{items.slice(0, 8).map((x) => <li key={x.id}>• {x.nombre} <span className="opacity-70">— {x.de}{fecha && x.vence_en ? `, vence ${fechaCorta(x.vence_en)}` : ""}</span></li>)}
      {items.length > 8 && <li className="opacity-70">y {items.length - 8} más…</li>}</ul></div>;
}

function Datos({ e, cat, onCerrar, onGuardar }: { e: any; cat: any; onCerrar: () => void; onGuardar: (d: any) => void }) {
  const [f, setF] = useState<any>({ titulo: e.titulo, inmueble: e.inmueble || "", folio_real: e.folio_real || "", clave_catastral: e.clave_catastral || "", valor_operacion: e.valor_operacion || "",
    responsable_id: e.responsable_id ? String(e.responsable_id) : "", cita_firma: local(e.cita_firma), cita_lugar: e.cita_lugar || "", numero_escritura: e.numero_escritura || "",
    volumen: e.volumen || "", folio_registro: e.folio_registro || "", mensaje_cliente: e.mensaje_cliente || "", notas: e.notas || "" });
  const c = (k: string) => ({ value: f[k] ?? "", onChange: (ev: any) => setF({ ...f, [k]: ev.target.value }) });
  const n = (v: string) => v || null;
  return (
    <Modal titulo="Datos del expediente" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(ev) => { ev.preventDefault(); onGuardar({ acto: e.acto, ...f, inmueble: n(f.inmueble), folio_real: n(f.folio_real), clave_catastral: n(f.clave_catastral),
        valor_operacion: n(f.valor_operacion), responsable_id: f.responsable_id ? Number(f.responsable_id) : null, cita_firma: f.cita_firma ? new Date(f.cita_firma).toISOString() : null,
        cita_lugar: n(f.cita_lugar), numero_escritura: n(f.numero_escritura), volumen: n(f.volumen), folio_registro: n(f.folio_registro), mensaje_cliente: n(f.mensaje_cliente), notas: n(f.notas) }); }}>
        <label className="sm:col-span-2"><span className="etiqueta">Nombre del expediente</span><input className="campo" required minLength={3} {...c("titulo")} /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Inmueble</span><input className="campo" {...c("inmueble")} /></label>
        <label><span className="etiqueta">Folio real</span><input className="campo" {...c("folio_real")} /></label>
        <label><span className="etiqueta">Clave catastral</span><input className="campo" {...c("clave_catastral")} /></label>
        <label><span className="etiqueta">Cita de firma</span><input className="campo" type="datetime-local" {...c("cita_firma")} /></label>
        <label><span className="etiqueta">Lugar de la firma</span><input className="campo" {...c("cita_lugar")} /></label>
        <label><span className="etiqueta">Número de escritura</span><input className="campo" {...c("numero_escritura")} /></label>
        <label><span className="etiqueta">Volumen</span><input className="campo" {...c("volumen")} /></label>
        <label><span className="etiqueta">Entrada al Registro Público</span><input className="campo" placeholder="Folio o número de entrada" {...c("folio_registro")} /></label>
        <label><span className="etiqueta">Responsable</span><select className="campo" {...c("responsable_id")}><option value="">—</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Valor de la operación</span><input className="campo" inputMode="decimal" value={f.valor_operacion} onChange={(ev) => setF({ ...f, valor_operacion: ev.target.value.replace(/[^\d.]/g, "") })} /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Aviso para el cliente (lo ve en su enlace)</span><textarea className="campo" rows={2} placeholder="Ej. Traiga su INE original el día de la firma." {...c("mensaje_cliente")} /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Notas internas (nunca se comparten)</span><textarea className="campo" rows={2} {...c("notas")} /></label>
        <p className="text-xs text-slate-500 sm:col-span-2">La entrada al Registro se muestra al cliente solo cuando marque como hecha la etapa «Ingreso al Registro Público».</p>
        <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function Hito({ h, onCerrar, onGuardar }: { h: any; onCerrar: () => void; onGuardar: (d: any) => void }) {
  const [f, setF] = useState({ estado: h.estado, fecha: h.fecha || "", nota_publica: h.nota_publica || "", visible_cliente: h.visible_cliente });
  return (
    <Modal titulo={h.nombre} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(ev) => { ev.preventDefault(); onGuardar({ ...f, fecha: f.fecha || null, nota_publica: f.nota_publica || null }); }}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{Object.entries(ESTADO_HITO).map(([k, [t]]) => (
          <label key={k} className={`flex cursor-pointer items-center gap-2 rounded-xl border p-2 text-sm ${f.estado === k ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
            <input type="radio" checked={f.estado === k} onChange={() => setF({ ...f, estado: k })} /> {t}</label>))}</div>
        <label className="block"><span className="etiqueta">Fecha</span><input className="campo" type="date" value={f.fecha} onChange={(ev) => setF({ ...f, fecha: ev.target.value })} /></label>
        <label className="block"><span className="etiqueta">Nota para el cliente {f.estado === "observado" && "(obligatoria: qué pidió el Registro o qué falta)"}</span>
          <textarea className="campo" rows={2} value={f.nota_publica} onChange={(ev) => setF({ ...f, nota_publica: ev.target.value })} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.visible_cliente} onChange={(ev) => setF({ ...f, visible_cliente: ev.target.checked })} /> Mostrar esta etapa en el seguimiento en línea</label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function ReqEstado({ r, modo, onCerrar, onGuardar, onBorrar }: { r: any; modo: "validar" | "mas"; onCerrar: () => void; onGuardar: (d: any) => void; onBorrar?: () => void }) {
  const [f, setF] = useState({ estado: modo === "validar" ? "validado" : r.estado, expedido_en: r.expedido_en || "", vence_en: r.vence_en || "", vigencia_dias: r.vigencia_dias ? String(r.vigencia_dias) : "",
    obligatorio: r.obligatorio, nota: r.nota || "" });
  return (
    <Modal titulo={r.nombre} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(ev) => { ev.preventDefault(); onGuardar({ ...f, expedido_en: f.expedido_en || null, vence_en: f.vence_en || null,
        vigencia_dias: f.vigencia_dias ? Number(f.vigencia_dias) : null, nota: f.nota || null }); }}>
        <p className="text-xs text-slate-500">De: {r.de}</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{Object.entries(ESTADO_REQ).map(([k, [t]]) => (
          <label key={k} className={`flex cursor-pointer items-center gap-2 rounded-xl border p-2 text-sm ${f.estado === k ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
            <input type="radio" checked={f.estado === k} onChange={() => setF({ ...f, estado: k })} /> {k === "pendiente" ? "Falta" : t}</label>))}</div>
        <div className="grid gap-3 sm:grid-cols-3">
          <label><span className="etiqueta">Fecha de expedición</span><input className="campo" type="date" max={hoyLocal()} value={f.expedido_en} onChange={(ev) => setF({ ...f, expedido_en: ev.target.value, vence_en: "" })} /></label>
          <label><span className="etiqueta">Vigencia (días)</span><input className="campo" type="number" min={1} value={f.vigencia_dias} onChange={(ev) => setF({ ...f, vigencia_dias: ev.target.value, vence_en: "" })} /></label>
          <label><span className="etiqueta">Vence (o calcúlelo)</span><input className="campo" type="date" value={f.vence_en} onChange={(ev) => setF({ ...f, vence_en: ev.target.value })} /></label>
        </div>
        {f.estado === "rechazado" && <label className="block"><span className="etiqueta">¿Qué hay que corregir? (lo ve el cliente)</span><input className="campo" required value={f.nota} onChange={(ev) => setF({ ...f, nota: ev.target.value })} /></label>}
        {modo === "mas" && f.estado !== "rechazado" && <label className="block"><span className="etiqueta">Nota</span><input className="campo" value={f.nota} onChange={(ev) => setF({ ...f, nota: ev.target.value })} /></label>}
        {modo === "mas" && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.obligatorio} onChange={(ev) => setF({ ...f, obligatorio: ev.target.checked })} /> Obligatorio para firmar</label>}
        <div className="flex justify-between gap-2">{modo === "mas" && onBorrar ? <button type="button" className="text-sm text-red-700 underline" onClick={onBorrar}>Quitar de la lista</button> : <span />}
          <span className="flex gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></span></div>
      </form>
    </Modal>
  );
}

function NuevoReq({ e, onCerrar, onGuardar }: { e: any; onCerrar: () => void; onGuardar: (d: any) => void }) {
  const [f, setF] = useState({ nombre: "", parte_id: "", obligatorio: true, vigencia_dias: "" });
  return (
    <Modal titulo="Agregar documento" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(ev) => { ev.preventDefault(); onGuardar({ nombre: f.nombre, parte_id: f.parte_id ? Number(f.parte_id) : null, obligatorio: f.obligatorio, vigencia_dias: f.vigencia_dias ? Number(f.vigencia_dias) : null }); }}>
        <label className="block"><span className="etiqueta">Documento</span><input className="campo" required minLength={2} value={f.nombre} onChange={(ev) => setF({ ...f, nombre: ev.target.value })} placeholder="Ej. Constancia de zonificación" /></label>
        <label className="block"><span className="etiqueta">¿De quién?</span><select className="campo" value={f.parte_id} onChange={(ev) => setF({ ...f, parte_id: ev.target.value })}>
          <option value="">Del inmueble u operación</option>{e.partes.map((p: any) => <option key={p.id} value={p.id}>{p.rol_texto}: {p.nombre}</option>)}</select></label>
        <label className="block"><span className="etiqueta">Vigencia en días (opcional)</span><input className="campo" type="number" min={1} value={f.vigencia_dias} onChange={(ev) => setF({ ...f, vigencia_dias: ev.target.value })} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.obligatorio} onChange={(ev) => setF({ ...f, obligatorio: ev.target.checked })} /> Obligatorio para firmar</label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Agregar</button></div>
      </form>
    </Modal>
  );
}

function NuevaParte({ cat, onCerrar, onGuardar }: { cat: any; onCerrar: () => void; onGuardar: (d: any) => void }) {
  const [f, setF] = useState({ rol: "comprador", nombre: "", email: "", tipo: "fisica", casado: false });
  const [cli, setCli] = useState<ClienteBreve | null>(null);
  return (
    <Modal titulo="Agregar parte" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(ev) => { ev.preventDefault(); onGuardar({ ...f, cr_cliente_id: cli?.id ?? null, nombre: cli ? null : f.nombre, email: cli ? null : f.email || null }); }}>
        <label className="block"><span className="etiqueta">Rol</span><select className="campo" value={f.rol} onChange={(ev) => setF({ ...f, rol: ev.target.value })}>{Object.entries(cat.roles).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
        <SelectorCliente valor={cli} onCambio={setCli} etiqueta="Persona (de su directorio de Clientes)" />
        {!cli && <div className="grid gap-2 sm:grid-cols-2"><input className="campo" placeholder="…o escriba el nombre" value={f.nombre} onChange={(ev) => setF({ ...f, nombre: ev.target.value })} aria-label="Nombre" />
          <input className="campo" type="email" placeholder="Correo" value={f.email} onChange={(ev) => setF({ ...f, email: ev.target.value })} aria-label="Correo" />
          <select className="campo" value={f.tipo} onChange={(ev) => setF({ ...f, tipo: ev.target.value })} aria-label="Tipo"><option value="fisica">Persona física</option><option value="moral">Persona moral</option></select></div>}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.casado} onChange={(ev) => setF({ ...f, casado: ev.target.checked })} /> Casado(a)</label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Agregar</button></div>
      </form>
    </Modal>
  );
}

function Compartir({ e, onCerrar }: { e: any; onCerrar: () => void }) {
  const [f, setF] = useState<any>({ tipo: "parte", parte_id: e.partes[0] ? String(e.partes[0].id) : "", nombre: "", email: "", avisar: true, dias: "180" });
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [copiado, setCopiado] = useState(false);
  const parte = e.partes.find((p: any) => String(p.id) === f.parte_id);
  async function crear(ev: React.FormEvent) {
    ev.preventDefault(); setError("");
    try { setR(await api.post(`/escrituracion/expedientes/${e.id}/accesos`, { tipo: f.tipo, parte_id: f.tipo === "parte" ? Number(f.parte_id) : null, nombre: f.nombre || null,
      email: f.email || null, avisar: f.avisar, dias: Number(f.dias) })); } catch (x: any) { setError(x.message); }
  }
  const mensaje = r ? `Hola${f.tipo === "parte" && parte ? `, ${parte.nombre.split(" ")[0]}` : ""}. Aquí puede ver en línea el avance de su trámite y subir los documentos que se le piden: ${r.enlace}` : "";
  return (
    <Modal titulo="Compartir el avance del trámite" onCerrar={onCerrar} ancho="max-w-xl">
      {!r ? <form className="space-y-3" onSubmit={crear}>
        <div className="flex flex-wrap gap-3 text-sm">{[["parte", "Una de las partes"], ["inmobiliaria", "Inmobiliaria o asesor"], ["banco", "Banco"], ["otro", "Otra persona"]].map(([k, t]) =>
          <label key={k} className="flex items-center gap-2"><input type="radio" checked={f.tipo === k} onChange={() => setF({ ...f, tipo: k })} /> {t}</label>)}</div>
        {f.tipo === "parte" ? <label className="block"><span className="etiqueta">¿Quién?</span><select className="campo" value={f.parte_id} onChange={(ev) => setF({ ...f, parte_id: ev.target.value })}>
          {e.partes.map((p: any) => <option key={p.id} value={p.id}>{p.rol_texto}: {p.nombre}</option>)}</select></label>
          : <label className="block"><span className="etiqueta">Nombre</span><input className="campo" required value={f.nombre} onChange={(ev) => setF({ ...f, nombre: ev.target.value })} placeholder={f.tipo === "banco" ? "Ej. Banco — ejecutivo hipotecario" : "Ej. Inmobiliaria Ficticia"} /></label>}
        <label className="block"><span className="etiqueta">Correo para avisarle cada avance {f.tipo === "parte" && parte?.email ? `(si lo deja vacío: ${parte.email})` : "(opcional)"}</span>
          <input className="campo" type="email" value={f.email} onChange={(ev) => setF({ ...f, email: ev.target.value })} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.avisar} onChange={(ev) => setF({ ...f, avisar: ev.target.checked })} /> Avisarle por correo cuando avance una etapa</label>
        <label className="block"><span className="etiqueta">Vigencia del enlace</span><select className="campo" value={f.dias} onChange={(ev) => setF({ ...f, dias: ev.target.value })}>
          {[["30", "1 mes"], ["90", "3 meses"], ["180", "6 meses"], ["365", "1 año"]].map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
        <p className="text-xs text-slate-500">{f.tipo === "banco" ? "El banco solo consulta el avance; no ve ni sube documentos." : f.tipo === "parte" ? "Verá y podrá subir solo sus documentos (y los del inmueble si es quien vende o dona)." : "Podrá ver y subir los documentos pendientes de la operación."}</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Crear enlace</button></div>
      </form> : <div className="space-y-3 text-sm">
        <Aviso tipo="ok">Enlace creado. {r.aviso}</Aviso>
        <textarea className="campo font-mono text-xs" rows={4} readOnly value={mensaje} aria-label="Mensaje con el enlace" />
        <div className="flex flex-wrap justify-end gap-2">
          <button className="btn-sec" onClick={() => { navigator.clipboard?.writeText(mensaje); setCopiado(true); }}>{copiado ? "¡Copiado!" : "Copiar mensaje"}</button>
          <a className="btn-sec" target="_blank" rel="noopener noreferrer" href={`https://wa.me/?text=${encodeURIComponent(mensaje)}`}>Enviar por WhatsApp</a>
          <button className="btn-turquesa" onClick={onCerrar}>Listo</button></div>
      </div>}
    </Modal>
  );
}
