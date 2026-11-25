"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import Shell from "@/components/Shell";
import { AccesoPortal, Chip, ESTADO_INC, FormEmpleado, FormIncidencia, fechaCorta } from "@/components/rh";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { api, mxn } from "@/lib/api";

const ESTADO_DOC: Record<string, [string, string]> = { aceptado: ["Aceptado", "bg-emerald-100 text-emerald-800"], por_revisar: ["Por revisar", "bg-amber-100 text-amber-800"],
  rechazado: ["Rechazado", "bg-red-100 text-red-800"] };

export default function Ficha() {
  const { id } = useParams<{ id: string }>();
  const [e, setE] = useState<any>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [dlg, setDlg] = useState<any>(null);
  const [tipoDoc, setTipoDoc] = useState("ine");
  const archivo = useRef<HTMLInputElement>(null);
  const [error, setError] = useState(""); const [ok, setOk] = useState("");
  const cargar = useCallback(() => api.get(`/rh/empleados/${id}`).then(setE).catch((x) => setError(x.message)), [id]);
  useEffect(() => { cargar(); api.get("/rh/resumen").then(setCfg).catch(() => {}); }, [cargar]);
  async function hacer(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await f(); setOk(msg); await cargar(); } catch (x: any) { setError(x.message); }
  }
  async function subir(ev: React.FormEvent) {
    ev.preventDefault();
    const a = archivo.current?.files?.[0]; if (!a) return;
    const d = new FormData(); d.append("tipo", tipoDoc); d.append("archivo", a);
    await hacer(() => api.subir(`/rh/empleados/${id}/documentos`, d), "Documento guardado.");
    if (archivo.current) archivo.current.value = "";
  }
  if (!e || !cfg) return <Shell><Aviso>{error}</Aviso></Shell>;
  const v = e.vacaciones;
  return (
    <Shell>
      <Link href="/rh" className="text-sm font-semibold text-turquesa-700">← Recursos humanos</Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">{e.nombre}</h1>
          <p className="text-sm text-slate-600">{[e.puesto, e.area, e.empresa].filter(Boolean).join(" · ")} · Ingresó el {fechaCorta(e.fecha_ingreso)}</p>
          {e.estado === "baja" && <p className="mt-1"><Chip e={[`Baja el ${fechaCorta(e.fecha_baja)}: ${e.motivo_baja}`, "bg-slate-200 text-slate-700"]} /></p>}</div>
        {cfg.puede_editar && <div className="flex flex-wrap gap-2">
          {e.estado === "activo" && <><button className="btn-turquesa" onClick={() => setDlg({ t: "portal" })}>{e.portal ? "Acceso al portal" : "Dar acceso al portal"}</button>
            <button className="btn-sec" onClick={() => setDlg({ t: "incidencia" })}>Registrar falta, permiso…</button></>}
          <button className="btn-sec" onClick={() => setDlg({ t: "editar" })}>Editar</button>
          {e.estado === "activo" ? <button className="btn-sec" onClick={() => setDlg({ t: "baja" })}>Dar de baja</button>
            : <button className="btn-sec" onClick={() => hacer(() => api.post(`/rh/empleados/${id}/reingreso`, {}), "Reingreso registrado.")}>Reingreso</button>}
        </div>}
      </div>
      <div className="my-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      <div className="grid gap-5 lg:grid-cols-3">
        <section className="tarjeta p-5" aria-label="Vacaciones">
          <h2 className="font-semibold text-marino">Vacaciones</h2>
          {v.anios === 0 ? <p className="mt-2 text-sm text-slate-600">Aún no cumple su primer año. El {fechaCorta(v.proximo_aniversario)} le corresponderán <b>{v.dias_proximo} días</b> (artículo 76 LFT).</p> : <>
            <p className="mt-2 text-4xl font-extrabold text-marino">{v.disponibles}<span className="text-base font-semibold text-slate-500"> días disponibles</span></p>
            <p className="text-sm text-slate-600">Le corresponden {v.derecho} por su {v.anios}.º año (art. 76 LFT); ha tomado {v.tomados}{v.pendientes_aprobar ? ` y pidió ${v.pendientes_aprobar} por autorizar` : ""}.</p>
            <p className="mt-1 text-xs text-slate-500">Periodo desde {fechaCorta(v.desde)}. Prima vacacional mínima de 25 %. Al {fechaCorta(v.proximo_aniversario)} sube a {v.dias_proximo} días.</p></>}
        </section>
        <section className="tarjeta p-5 lg:col-span-2" aria-label="Datos">
          <h2 className="font-semibold text-marino">Datos</h2>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
            {[["Salario diario", mxn(e.salario_diario)], ["Contrato", cfg.contratos[e.tipo_contrato]], ["RFC", e.rfc], ["CURP", e.curp], ["NSS", e.nss], ["Correo", e.email], ["Celular", e.telefono],
              ["Portal", e.portal ? (e.portal_ultimo_acceso ? `Entró el ${fechaCorta(e.portal_ultimo_acceso)}` : "Con acceso, aún no entra") : "Sin acceso"]].map(([k, x]) => (
              <div key={k as string}><dt className="text-xs text-slate-500">{k}</dt><dd className="text-slate-800">{x || "—"}</dd></div>))}</dl>
          {e.notas && <p className="mt-3 whitespace-pre-wrap rounded-lg bg-crema/60 p-3 text-sm">{e.notas}</p>}
        </section>
      </div>

      <section className="tarjeta mt-5 p-5" aria-label="Documentos">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold text-marino">Expediente de documentos</h2>
          {e.faltantes.length ? <span className="text-sm text-amber-700">Faltan: {e.faltantes.map((k: string) => cfg.documentos[k]).join(", ")}</span> : <span className="text-sm text-emerald-700">✓ Expediente completo</span>}</div>
        {e.documentos.length > 0 && <ul className="mt-2 divide-y divide-crema-200 text-sm">{e.documentos.map((d: any) => (
          <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span><b className="text-marino">{d.tipo_texto}</b> · {d.nombre} <Chip e={ESTADO_DOC[d.estado]} />{d.origen === "portal" && <span className="ml-1 text-xs text-slate-500">lo subió el empleado</span>}
              {d.nota && <span className="block text-xs text-red-700">{d.nota}</span>}</span>
            <span className="flex flex-wrap gap-3 text-xs"><button className="font-semibold text-turquesa-700 underline" onClick={() => api.descargar(`/rh/documentos/${d.id}`, d.nombre)}>Ver</button>
              {cfg.puede_editar && d.estado === "por_revisar" && <><button className="font-semibold text-emerald-700 underline" onClick={() => hacer(() => api.post(`/rh/documentos/${d.id}/revisar`, { aceptar: true }), "Documento aceptado.")}>Aceptar</button>
                <button className="text-red-700 underline" onClick={() => setDlg({ t: "rechazar_doc", d })}>Rechazar</button></>}
              {cfg.puede_editar && <button className="text-slate-500 underline" onClick={() => setDlg({ t: "borrar_doc", d })}>Borrar</button>}</span></li>))}</ul>}
        {cfg.puede_editar && <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={subir}>
          <label className="block"><span className="etiqueta">Tipo</span><select className="campo" value={tipoDoc} onChange={(x) => setTipoDoc(x.target.value)}>
            {Object.entries(cfg.documentos).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
          <label className="block"><span className="etiqueta">Archivo (PDF o foto)</span><input ref={archivo} className="campo" type="file" accept=".pdf,.jpg,.jpeg,.png" required /></label>
          <button className="btn-sec">Subir documento</button></form>}
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <section className="tarjeta p-5" aria-label="Incidencias">
          <h2 className="font-semibold text-marino">Vacaciones, permisos y faltas</h2>
          {!e.incidencias.length ? <p className="mt-2 text-sm text-slate-500">Sin registros.</p> : <ul className="mt-2 divide-y divide-crema-200 text-sm">{e.incidencias.map((i: any) => (
            <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2"><span><b>{i.tipo_texto}</b> · {i.dias} día{i.dias === 1 ? "" : "s"} <Chip e={ESTADO_INC[i.estado]} />
              <span className="block text-xs text-slate-500">{fechaCorta(i.desde)}{i.hasta !== i.desde ? ` al ${fechaCorta(i.hasta)}` : ""}{i.motivo ? ` · ${i.motivo}` : ""}{i.comentario ? ` · RH: ${i.comentario}` : ""}</span></span>
              {cfg.puede_editar && i.estado === "pendiente" && <span className="flex gap-2 text-xs"><button className="font-semibold text-emerald-700 underline" onClick={() => hacer(() => api.post(`/rh/incidencias/${i.id}/resolver`, { aprobar: true }), "Autorizada.")}>Autorizar</button></span>}
              {cfg.puede_editar && i.estado === "aprobada" && <button className="text-xs text-slate-500 underline" onClick={() => hacer(() => api.borrar(`/rh/incidencias/${i.id}`), "Cancelada.")}>Cancelar</button>}</li>))}</ul>}
        </section>
        <section className="tarjeta p-5" aria-label="Recibos">
          <h2 className="font-semibold text-marino">Recibos de nómina</h2>
          {!e.recibos.length ? <p className="mt-2 text-sm text-slate-500">Aún no hay recibos. Se generan al armar un periodo en la pestaña «Nómina».</p> : <ul className="mt-2 divide-y divide-crema-200 text-sm">{e.recibos.map((r: any) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2"><Link href={`/rh/nomina/${r.periodo_id}`} className="hover:underline">{fechaCorta(r.inicio)} al {fechaCorta(r.fin)}</Link>
              <span className="flex items-center gap-3"><b>{mxn(r.neto)}</b>{r.estado === "borrador" ? <Chip e={["Borrador", "bg-amber-100 text-amber-800"]} /> : r.visto ? <span className="text-xs text-emerald-700">✓ Lo descargó</span> : null}
                <button className="text-xs font-semibold text-turquesa-700 underline" onClick={() => api.descargar(`/rh/recibos/${r.id}/pdf`, "recibo.pdf")}>PDF</button></span></li>))}</ul>}
        </section>
      </div>
      {cfg.es_admin && <button className="mt-6 text-xs text-red-700 underline" onClick={() => setDlg({ t: "borrar" })}>Borrar expediente completo (derechos ARCO)</button>}

      {dlg?.t === "editar" && <FormEmpleado cfg={cfg} empleado={e} onCerrar={() => setDlg(null)} onListo={() => { setDlg(null); setOk("Datos guardados."); cargar(); }} />}
      {dlg?.t === "incidencia" && <FormIncidencia cfg={cfg} empleado={e} onCerrar={() => setDlg(null)} onListo={() => { setDlg(null); setOk("Registrado."); cargar(); }} />}
      {dlg?.t === "portal" && <AccesoPortal empleado={e} onCerrar={() => { setDlg(null); cargar(); }} />}
      {dlg?.t === "baja" && <Baja id={id} onCerrar={() => setDlg(null)} onListo={() => { setDlg(null); setOk("Baja registrada. Su acceso al portal quedó cancelado."); cargar(); }} />}
      {dlg?.t === "rechazar_doc" && <RechazarDoc d={dlg.d} onCerrar={() => setDlg(null)} onListo={() => { setDlg(null); setOk("Documento rechazado; el empleado verá qué corregir."); cargar(); }} />}
      {dlg?.t === "borrar_doc" && <ConfirmarEliminar titulo="Borrar documento" onCerrar={() => setDlg(null)} onConfirmar={() => api.borrar(`/rh/documentos/${dlg.d.id}`).then(cargar)}>¿Borrar {dlg.d.tipo_texto}?</ConfirmarEliminar>}
      {dlg?.t === "borrar" && <ConfirmarEliminar titulo="Borrar expediente" onCerrar={() => setDlg(null)} onConfirmar={() => api.borrar(`/rh/empleados/${id}`).then(() => { window.location.href = "/rh"; })}>
        Se borran para siempre los datos, documentos, incidencias y recibos de {e.nombre}. Úselo solo si la persona lo pidió o fue un error de captura.</ConfirmarEliminar>}
    </Shell>
  );
}

function Baja({ id, onCerrar, onListo }: { id: string; onCerrar: () => void; onListo: () => void }) {
  const [f, setF] = useState({ fecha: new Date().toLocaleDateString("en-CA"), motivo: "" }); const [error, setError] = useState("");
  return <Modal titulo="Dar de baja" onCerrar={onCerrar}>
    <form className="space-y-3" onSubmit={async (ev) => { ev.preventDefault(); try { await api.post(`/rh/empleados/${id}/baja`, f); onListo(); } catch (x: any) { setError(x.message); } }}>
      <label className="block"><span className="etiqueta">Fecha de baja</span><input className="campo" type="date" value={f.fecha} onChange={(x) => setF({ ...f, fecha: x.target.value })} required /></label>
      <label className="block"><span className="etiqueta">Motivo</span><input className="campo" value={f.motivo} onChange={(x) => setF({ ...f, motivo: x.target.value })} required minLength={3} placeholder="Renuncia voluntaria, término de contrato…" /></label>
      <p className="text-xs text-slate-500">¿Necesita el finiquito? Calcúlelo en Liquidaciones LFT con su salario y antigüedad.</p>
      <Aviso>{error}</Aviso><div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Dar de baja</button></div>
    </form></Modal>;
}

function RechazarDoc({ d, onCerrar, onListo }: { d: any; onCerrar: () => void; onListo: () => void }) {
  const [n, setN] = useState(""); const [error, setError] = useState("");
  return <Modal titulo={`Rechazar ${d.tipo_texto}`} onCerrar={onCerrar}>
    <form className="space-y-3" onSubmit={async (ev) => { ev.preventDefault(); try { await api.post(`/rh/documentos/${d.id}/revisar`, { aceptar: false, nota: n }); onListo(); } catch (x: any) { setError(x.message); } }}>
      <label className="block"><span className="etiqueta">¿Qué debe corregir? (lo verá el empleado)</span><input className="campo" value={n} onChange={(x) => setN(x.target.value)} required maxLength={300} placeholder="La foto se ve borrosa; súbala de nuevo." /></label>
      <Aviso>{error}</Aviso><div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Rechazar</button></div>
    </form></Modal>;
}
