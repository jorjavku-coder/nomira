"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AforeShell, COLOR_CASO, COLOR_REQ, CampoDato, Pastilla, TarjetaMensaje, mxnTexto, useCatalogos } from "@/components/afore";
import { useSesion } from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha, fechaHora, hoyLocal } from "@/lib/api";

type Pestana = "resumen" | "checklist" | "documentos" | "seguimiento" | "revision" | "portal" | "afore" | "evidencia" | "historial";

export default function CasoAfore() {
  const { id } = useParams<{ id: string }>();
  const cat = useCatalogos();
  const sesion = useSesion();
  const editor = !!sesion && sesion.usuario.rol !== "consulta";
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [pestana, setPestana] = useState<Pestana>("resumen");
  const cargar = useCallback(() => api.get(`/afore/casos/${id}`).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function accion(fn: () => Promise<any>, mensaje = "") {
    setError(""); setOk("");
    try { const r = await fn(); if (mensaje) setOk(mensaje); await cargar(); return r ?? true; } catch (e: any) { setError(e.message); }
  }
  if (!d || !cat) return <AforeShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AforeShell>;
  const c = d.caso;
  const pend = d.requisitos.filter((r: any) => ["solicitado", "requiere_correccion"].includes(r.estado)).length;
  const porRevisar = d.requisitos.filter((r: any) => ["recibido", "por_revisar"].includes(r.estado)).length;
  const msjPend = d.mensajes.filter((x: any) => ["esperando_aprobacion", "fallido", "borrador"].includes(x.estado)).length;
  const tabs: [Pestana, string, number?][] = [
    ["resumen", "Resumen"], ["checklist", "Checklist", pend + porRevisar], ["documentos", "Documentos", d.documentos.length],
    ["seguimiento", "Seguimiento", d.actividades.length], ["revision", "¿Expediente listo?"], ["portal", "Portal y mensajes", msjPend],
    ["afore", "Localizar AFORE y CURP"], ...(cat.evidencia_activa ? [["evidencia", "Evidencia"] as [Pestana, string]] : []), ["historial", "Historial"],
  ];
  const ctx = { d, c, id, cat, editor, accion, setError };
  return (
    <AforeShell>
      <Link href="/afore/casos" className="text-sm text-turquesa-700 hover:underline">← Casos AFORE</Link>
      <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-extrabold text-marino">{c.cliente}</h1>
            <Pastilla clase={COLOR_CASO[c.estado]}>{c.estado_texto}</Pastilla>
            {c.restringido && <Pastilla clase="bg-red-100 text-red-800">Restringido</Pastilla>}
          </div>
          <p className="mt-1 text-sm text-slate-600">{[c.tipo_texto, c.titular_nombre && `Titular: ${c.titular_nombre}`, c.identificador_interno && `Ref. ${c.identificador_interno}`,
            c.responsable ? `Responsable: ${c.responsable}` : "Sin responsable"].filter(Boolean).join(" · ")}</p>
          <p className="text-xs text-slate-500"><Link className="hover:underline" href={`/afore/clientes/${c.cliente_id}`}>Ver ficha del cliente</Link> · {d.cliente.relacion_texto} · titular: {d.cliente.titular_estado_texto}</p>
        </div>
        {editor && (
          <div className="flex flex-wrap gap-2">
            {c.estado === "borrador" && <button className="btn-turquesa" onClick={() => accion(() => api.patch(`/afore/casos/${id}`, { estado: "abierto" }), "Caso abierto.")}>Abrir el caso</button>}
            <select className="campo w-auto" value={c.estado} aria-label="Estado del caso" onChange={(e) => accion(() => api.patch(`/afore/casos/${id}`, { estado: e.target.value }), "Estado actualizado.")}>
              {Object.entries(cat.estados_caso).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
            </select>
          </div>
        )}
      </div>
      <div className="mt-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mb-5 mt-4 flex gap-1 overflow-x-auto border-b border-crema-300" role="tablist">
        {tabs.map(([k, t, n]) => (
          <button key={k} role="tab" aria-selected={pestana === k} onClick={() => setPestana(k)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${pestana === k ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>
            {t}{n ? <span className="ml-1.5 rounded-full bg-amber-100 px-1.5 text-[11px] text-amber-800">{n}</span> : null}</button>))}
      </div>
      {pestana === "resumen" && <Resumen {...ctx} />}
      {pestana === "checklist" && <Checklist {...ctx} />}
      {pestana === "documentos" && <Documentos {...ctx} />}
      {pestana === "seguimiento" && <Seguimiento {...ctx} />}
      {pestana === "revision" && <Revision id={id} />}
      {pestana === "portal" && <Portal {...ctx} />}
      {pestana === "afore" && <LocalizarCurp {...ctx} />}
      {pestana === "evidencia" && <Evidencia {...ctx} />}
      {pestana === "historial" && <Historial id={id} />}
    </AforeShell>
  );
}

// ------------------------------------------------------------------ Resumen

function Resumen({ c, id, cat, editor, accion }: any) {
  const [f, setF] = useState({ siguiente_actividad: c.siguiente_actividad || "", siguiente_fecha: c.siguiente_fecha || "", siguiente_responsable_id: c.siguiente_responsable_id ? String(c.siguiente_responsable_id) : "",
    responsable_id: c.responsable_id ? String(c.responsable_id) : "", resumen_interno: "" });
  const [datos, setDatos] = useState<any>(c.datos);
  const [editarDatos, setEditarDatos] = useState(false);
  const cambiar = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const mostrar = (k: string) => {
    const x = c.datos[k];
    if (!x) return <span className="text-slate-400">Sin capturar</span>;
    if (x.estado !== "informado") return <span className="text-amber-700">{cat.estados_dato[x.estado]}</span>;
    return k.startsWith("monto") ? <>{mxnTexto(x.valor)} <span className="text-[11px] text-slate-500">(dato informado)</span></> : x.valor;
  };
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="tarjeta p-5">
        <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-marino">Instituciones y datos del caso</h2>
          {editor && <button className="text-sm font-semibold text-turquesa-700 hover:underline" onClick={() => setEditarDatos(true)}>Editar</button>}</div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          {Object.entries(cat.campos_dato).map(([k, t]: any) => <><dt key={k + "t"} className="text-slate-500">{t}</dt><dd key={k}>{mostrar(k)}</dd></>)}
        </dl>
        <p className="mt-3 text-xs text-slate-500">Los montos son datos capturados del cliente o la AFORE; Nomira no los verifica ni proyecta resultados.</p>
      </section>
      <section className="tarjeta p-5">
        <h2 className="mb-3 font-semibold text-marino">Siguiente actividad y responsables</h2>
        {editor ? (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault();
            accion(() => api.patch(`/afore/casos/${id}`, { siguiente_actividad: f.siguiente_actividad || null, siguiente_fecha: f.siguiente_fecha || null,
              siguiente_responsable_id: f.siguiente_responsable_id ? Number(f.siguiente_responsable_id) : null, responsable_id: f.responsable_id ? Number(f.responsable_id) : null,
              ...(f.resumen_interno ? { resumen_interno: f.resumen_interno } : {}) }), "Guardado."); }}>
            <label className="block"><span className="etiqueta">Siguiente actividad</span><input className="campo" maxLength={300} value={f.siguiente_actividad} onChange={cambiar("siguiente_actividad")} /></label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block"><span className="etiqueta">Fecha</span><input className="campo" type="date" value={f.siguiente_fecha} onChange={cambiar("siguiente_fecha")} /></label>
              <label className="block"><span className="etiqueta">La realiza</span><select className="campo" value={f.siguiente_responsable_id} onChange={cambiar("siguiente_responsable_id")}>
                <option value="">El responsable del caso</option>{cat.responsables.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
              <label className="block sm:col-span-2"><span className="etiqueta">Responsable del caso</span><select className="campo" value={f.responsable_id} onChange={cambiar("responsable_id")}>
                <option value="">Sin asignar</option>{cat.responsables.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
            </div>
            <button className="btn-primario">Guardar</button>
          </form>
        ) : <p className="text-sm">{c.siguiente_actividad || "Sin definir"} {c.siguiente_fecha && `· ${fecha(c.siguiente_fecha)}`}</p>}
      </section>
      {editarDatos && (
        <Modal titulo="Instituciones y datos del caso" onCerrar={() => setEditarDatos(false)} ancho="max-w-3xl">
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(cat.campos_dato).map(([k, t]: any) => (
              <CampoDato key={k} etiqueta={t} estados={cat.estados_dato} monto={k.startsWith("monto")} lista={k.startsWith("afore") ? cat.afores : k === "institucion" ? cat.instituciones : undefined}
                valor={datos[k]} onCambio={(v) => setDatos({ ...datos, [k]: v })} />))}
          </div>
          <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setEditarDatos(false)}>Cancelar</button>
            <button className="btn-primario" onClick={async () => { const r = await accion(() => api.patch(`/afore/casos/${id}`, { datos }), "Datos actualizados."); if (r) setEditarDatos(false); }}>Guardar</button></div>
        </Modal>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Checklist

function Checklist({ d, id, cat, editor, accion }: any) {
  const [nuevo, setNuevo] = useState("");
  const [subir, setSubir] = useState<any>(null);
  return (
    <div className="space-y-4">
      <Aviso tipo="info">Herramienta de organización editable: no es una lista definitiva de requisitos legales. «Visible para el cliente» controla si aparece en su portal.</Aviso>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Documento o dato</th><th>Estado</th><th>Cliente lo ve</th><th>Nota interna / indicación al cliente</th><th></th></tr></thead>
          <tbody>
            {d.requisitos.map((r: any) => {
              const docs = d.documentos.filter((x: any) => x.requisito_id === r.id);
              return (
                <tr key={r.id} className={r.estado === "no_aplica" ? "opacity-60" : ""}>
                  <td><div className="font-semibold">{r.nombre}</div>
                    {docs.map((x: any) => <div key={x.id} className="text-xs text-slate-500">📄 {x.nombre} · {x.origen === "cliente" ? "enviado por el cliente" : "cargado por el despacho"}</div>)}
                    <div className="text-[11px] text-slate-400">{r.actualizado_por ? `${r.actualizado_por}, ` : ""}{fechaHora(r.actualizado_en)}</div></td>
                  <td>{editor ? (
                    <select className={`campo w-auto py-1 text-xs font-semibold ${COLOR_REQ[r.estado]}`} value={r.estado} aria-label={`Estado de ${r.nombre}`}
                      onChange={(e) => accion(() => api.patch(`/afore/requisitos/${r.id}`, { estado: e.target.value }), "Checklist actualizado.")}>
                      {Object.entries(cat.estados_requisito).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}
                    </select>) : <Pastilla clase={COLOR_REQ[r.estado]}>{r.estado_texto}</Pastilla>}</td>
                  <td><input type="checkbox" disabled={!editor} checked={r.visible_cliente} aria-label="Visible para el cliente"
                    onChange={(e) => accion(() => api.patch(`/afore/requisitos/${r.id}`, { visible_cliente: e.target.checked }))} /></td>
                  <td className="space-y-1">
                    <input className="campo py-1 text-xs" disabled={!editor} placeholder="Nota interna" defaultValue={r.nota || ""} maxLength={500}
                      onBlur={(e) => e.target.value !== (r.nota || "") && accion(() => api.patch(`/afore/requisitos/${r.id}`, { nota: e.target.value || null }))} />
                    <input className="campo py-1 text-xs" disabled={!editor} placeholder="Indicación para el cliente (la ve en su portal)" defaultValue={r.nota_cliente || ""} maxLength={300}
                      onBlur={(e) => e.target.value !== (r.nota_cliente || "") && accion(() => api.patch(`/afore/requisitos/${r.id}`, { nota_cliente: e.target.value || null }))} />
                  </td>
                  <td className="whitespace-nowrap text-right">{editor && <>
                    <button className="btn-sec mr-1" onClick={() => setSubir(r)}>Cargar</button>
                    <button className="btn-peligro" aria-label={`Quitar ${r.nombre}`} onClick={() => { if (confirm(`¿Quitar «${r.nombre}» del checklist?`)) accion(() => api.borrar(`/afore/requisitos/${r.id}`), "Quitado."); }}>✕</button></>}</td>
                </tr>);
            })}
          </tbody>
        </table>
      </div>
      {editor && (
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); accion(() => api.post(`/afore/casos/${id}/requisitos`, { nombre: nuevo }), "Agregado.").then((r: any) => r && setNuevo("")); }}>
          <input className="campo max-w-md" required minLength={2} maxLength={200} placeholder="Agregar documento o dato al checklist" value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
          <button className="btn-turquesa">Agregar</button>
        </form>
      )}
      {subir && <CargarDocumento id={id} requisito={subir} onCerrar={() => setSubir(null)} accion={accion} />}
    </div>
  );
}

function CargarDocumento({ id, requisito, onCerrar, accion }: any) {
  const archivo = useRef<HTMLInputElement>(null);
  const [visible, setVisible] = useState(false);
  return (
    <Modal titulo={requisito ? `Cargar: ${requisito.nombre}` : "Cargar documento"} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        const f = archivo.current?.files?.[0];
        if (!f) return;
        const fd = new FormData();
        fd.append("archivo", f); fd.append("visible_cliente", String(visible));
        if (requisito) fd.append("requisito_id", String(requisito.id));
        const r = await accion(() => api.subir(`/afore/casos/${id}/documentos`, fd), "Documento cargado.");
        if (r) onCerrar();
      }}>
        <input ref={archivo} type="file" required accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" className="block text-sm" />
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={visible} onChange={(e) => setVisible(e.target.checked)} /> El cliente puede ver este documento en su portal</label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Cargar</button></div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ Documentos

function Documentos({ d, id, editor, accion }: any) {
  const [subir, setSubir] = useState(false);
  const [capturar, setCapturar] = useState<any>(null);
  const reqs = Object.fromEntries(d.requisitos.map((r: any) => [r.id, r.nombre]));
  return (
    <div className="space-y-4">
      {editor && <button className="btn-turquesa" onClick={() => setSubir(true)}>Cargar documento</button>}
      <p className="text-xs text-slate-500">Los documentos enviados por el cliente quedan por revisar hasta que el despacho confirme su recepción. No hay análisis antivirus en el servidor: revíselos antes de abrirlos fuera de Nomira.</p>
      {d.documentos.length === 0 ? <div className="tarjeta p-8 text-center text-sm text-slate-500">Aún no hay documentos.</div> : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Documento</th><th>Para</th><th>Estado</th><th>Recepción</th><th>Cliente lo ve</th><th></th></tr></thead>
            <tbody>
              {d.documentos.map((x: any) => (
                <tr key={x.id} className={x.origen === "cliente" && !x.recepcion_confirmada_en ? "bg-violet-50/50" : ""}>
                  <td><div className="font-semibold">{x.nombre}</div><div className="text-xs text-slate-500">{x.origen === "cliente" ? "Enviado por el cliente" : x.subido_por} · {fechaHora(x.creado_en)}</div>
                    {Object.keys(x.datos_capturados).length > 0 && <div className="text-xs text-slate-500">Datos capturados: {Object.entries(x.datos_capturados).map(([k, v]) => `${k}: ${v}`).join(" · ")}</div>}</td>
                  <td className="text-sm">{reqs[x.requisito_id] || "—"}</td>
                  <td>{editor ? <select className="campo w-auto py-1 text-xs" value={x.estado} aria-label="Estado del documento"
                    onChange={(e) => accion(() => api.patch(`/afore/documentos/${x.id}`, { estado: e.target.value }), "Estado actualizado.")}>
                    <option value="recibido">Por revisar</option><option value="aceptado">Aceptado por el despacho</option><option value="requiere_correccion">Requiere corrección</option></select> : x.estado}</td>
                  <td className="text-xs">{x.recepcion_confirmada_en ? `Confirmada ${fechaHora(x.recepcion_confirmada_en)}` : editor ? (
                    <button className="btn-primario py-1 text-xs" onClick={() => accion(() => api.patch(`/afore/documentos/${x.id}`, { confirmar_recepcion: true }), "Recepción confirmada.")}>Confirmar recepción</button>) : "Pendiente"}</td>
                  <td><input type="checkbox" disabled={!editor} checked={x.visible_cliente} aria-label="Visible para el cliente"
                    onChange={(e) => accion(() => api.patch(`/afore/documentos/${x.id}`, { visible_cliente: e.target.checked }))} /></td>
                  <td className="whitespace-nowrap text-right">
                    <button className="btn-sec mr-1" onClick={() => api.descargar(`/afore/documentos/${x.id}/archivo`, x.nombre)}>Descargar</button>
                    {editor && <button className="btn-sec mr-1" title="Capture nombre, CURP, NSS o fechas que aparecen en el documento para detectar inconsistencias" onClick={() => setCapturar(x)}>Datos</button>}
                    {editor && <button className="btn-peligro" onClick={() => { if (confirm(`¿Eliminar «${x.nombre}»?`)) accion(() => api.borrar(`/afore/documentos/${x.id}`), "Eliminado."); }}>✕</button>}
                  </td>
                </tr>))}
            </tbody>
          </table>
        </div>
      )}
      {subir && <CargarDocumento id={id} onCerrar={() => setSubir(false)} accion={accion} />}
      {capturar && <CapturarDatos x={capturar} onCerrar={() => setCapturar(null)} accion={accion} />}
    </div>
  );
}

function CapturarDatos({ x, onCerrar, accion }: any) {
  const [f, setF] = useState<any>({ nombre: "", curp: "", nss: "", fecha_nacimiento: "", folio: "", ...x.datos_capturados });
  const campos: [string, string][] = [["nombre", "Nombre como aparece"], ["curp", "CURP como aparece"], ["nss", "NSS como aparece"], ["fecha_nacimiento", "Fecha de nacimiento"], ["folio", "Folio"]];
  return (
    <Modal titulo={`Datos que aparecen en «${x.nombre}»`} onCerrar={onCerrar}>
      <p className="mb-3 text-sm text-slate-500">Capture lo que usted lee en el documento. Nomira solo los compara con lo registrado para señalar posibles inconsistencias; no valida documentos.</p>
      <div className="space-y-2">{campos.map(([k, t]) => <label key={k} className="block"><span className="etiqueta">{t}</span><input className="campo" maxLength={120} value={f[k] || ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>)}</div>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
        <button className="btn-primario" onClick={async () => { const r = await accion(() => api.patch(`/afore/documentos/${x.id}`, { datos_capturados: f }), "Datos guardados."); if (r) onCerrar(); }}>Guardar</button></div>
    </Modal>
  );
}

// ------------------------------------------------------------------ Seguimiento

function Seguimiento({ d, id, cat, editor, accion }: any) {
  const hoy = hoyLocal();
  const vacioA = { tipo: "solicitud_enviada", fecha: hoy, institucion: "", canal: "", folio: "", resumen: "", responde_a_id: "", documento_id: "" };
  const [a, setA] = useState<any>(vacioA);
  const [p, setP] = useState<any>({ tipo: "seguimiento_interno", descripcion: "", fecha: "", fuente: "", regla: "" });
  const solicitudes = d.actividades.filter((x: any) => ["solicitud_enviada", "queja"].includes(x.tipo));
  const sugerir = (regla: any) => {
    const f = new Date(); f.setDate(f.getDate() + Number(regla.dias));
    setP({ ...p, tipo: "estimado", fecha: hoyLocal(f), regla: regla.nombre, fuente: regla.fuente || "", descripcion: p.descripcion || regla.nombre });
  };
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
      <section className="space-y-3">
        <h2 className="font-semibold text-marino">Cronología</h2>
        {editor && (
          <form className="tarjeta grid gap-2 p-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault();
            accion(() => api.post(`/afore/casos/${id}/actividades`, { ...a, institucion: a.institucion || null, canal: a.canal || null, folio: a.folio || null, resumen: a.resumen || null,
              responde_a_id: a.responde_a_id ? Number(a.responde_a_id) : null, documento_id: a.documento_id ? Number(a.documento_id) : null }), "Actividad registrada.").then((r: any) => r && setA(vacioA)); }}>
            <label className="block"><span className="etiqueta">Qué pasó</span><select className="campo" value={a.tipo} onChange={(e) => setA({ ...a, tipo: e.target.value })}>
              {Object.entries(cat.tipos_actividad).filter(([k]) => k !== "localizacion_afore").map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
            <label className="block"><span className="etiqueta">Fecha</span><input className="campo" type="date" required value={a.fecha} onChange={(e) => setA({ ...a, fecha: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Institución</span><input className="campo" list="inst" maxLength={120} value={a.institucion} onChange={(e) => setA({ ...a, institucion: e.target.value })} />
              <datalist id="inst">{[...cat.afores, ...cat.instituciones].map((x: string) => <option key={x} value={x} />)}</datalist></label>
            <label className="block"><span className="etiqueta">Canal</span><input className="campo" maxLength={60} placeholder="Sucursal, correo, portal…" value={a.canal} onChange={(e) => setA({ ...a, canal: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Folio</span><input className="campo" maxLength={80} value={a.folio} onChange={(e) => setA({ ...a, folio: e.target.value })} /></label>
            {a.tipo === "respuesta_recibida" ? (
              <label className="block"><span className="etiqueta">Responde a</span><select className="campo" value={a.responde_a_id} onChange={(e) => setA({ ...a, responde_a_id: e.target.value })}>
                <option value="">—</option>{solicitudes.map((x: any) => <option key={x.id} value={x.id}>{x.tipo_texto} {fecha(x.fecha)} {x.folio || ""}</option>)}</select></label>
            ) : <span />}
            <label className="block"><span className="etiqueta">Acuse o respuesta (documento)</span><select className="campo" value={a.documento_id} onChange={(e) => setA({ ...a, documento_id: e.target.value })}>
              <option value="">Ninguno</option>{d.documentos.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
            <label className="block sm:col-span-2"><span className="etiqueta">Resumen interno</span><textarea className="campo" rows={2} maxLength={5000} value={a.resumen} onChange={(e) => setA({ ...a, resumen: e.target.value })} /></label>
            <button className="btn-turquesa sm:col-span-2">Registrar</button>
          </form>
        )}
        {d.actividades.length === 0 && <div className="tarjeta p-6 text-center text-sm text-slate-500">Sin actividades registradas.</div>}
        <ol className="relative ml-3 space-y-3 border-l-2 border-crema-300 pl-6">
          {d.actividades.map((x: any) => (
            <li key={x.id} className="relative">
              <span className="absolute -left-[33px] top-4 h-4 w-4 rounded-full border-4 border-crema bg-turquesa" aria-hidden />
              <div className="tarjeta p-4 text-sm">
                <div className="flex flex-wrap items-center gap-2"><b className="font-marca text-marino">{fecha(x.fecha)}</b><Pastilla>{x.tipo_texto}</Pastilla>
                  {x.institucion && <span>{x.institucion}</span>}{x.canal && <span className="text-slate-500">· {x.canal}</span>}
                  {x.folio ? <span className="font-mono text-xs">Folio {x.folio}</span> : ["solicitud_enviada", "queja"].includes(x.tipo) && <span className="text-xs font-semibold text-amber-700">Sin folio</span>}</div>
                {x.resumen && <p className="mt-1 text-slate-700">{x.resumen}</p>}
                <p className="mt-1 text-xs text-slate-500">Registró {x.creado_por || "—"} · {fechaHora(x.creado_en)}{x.modificado_por && ` · modificó ${x.modificado_por}, ${fechaHora(x.modificado_en)}`}</p>
                {editor && !x.folio && ["solicitud_enviada", "queja"].includes(x.tipo) && (
                  <button className="mt-1 text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => {
                    const folio = prompt("Folio:"); if (folio) accion(() => api.patch(`/afore/actividades/${x.id}`, { tipo: x.tipo, fecha: x.fecha, folio }), "Folio registrado."); }}>Registrar folio</button>)}
              </div>
            </li>))}
        </ol>
      </section>
      <section className="space-y-3">
        <h2 className="font-semibold text-marino">Fechas y plazos</h2>
        <Aviso tipo="info">Nomira no trae plazos legales de fábrica. Un plazo legal solo existe si el abogado lo confirma con su fuente; las reglas del despacho solo sugieren fechas estimadas.</Aviso>
        {d.plazos.map((x: any) => (
          <div key={x.id} className={`tarjeta p-3 text-sm ${x.completado_en ? "opacity-60" : x.vencido ? "border-red-300" : ""}`}>
            <div className="flex flex-wrap items-center justify-between gap-2"><b className={x.vencido ? "text-red-700" : "text-marino"}>{fecha(x.fecha)}</b>
              <Pastilla clase={x.tipo === "legal_confirmado" ? "bg-red-50 text-red-800" : x.tipo === "estimado" ? "bg-slate-100 text-slate-600" : "bg-turquesa-50 text-turquesa-700"}>{x.tipo_texto}</Pastilla></div>
            <p>{x.descripcion}</p>
            {x.fuente && <p className="text-xs text-slate-500">Fuente: {x.fuente}</p>}
            {x.regla && <p className="text-xs text-slate-500">Sugerido por la regla «{x.regla}»</p>}
            {x.confirmado_por && <p className="text-xs text-slate-500">Confirmado por {x.confirmado_por}, {fechaHora(x.confirmado_en)}</p>}
            {editor && <div className="mt-1 flex gap-3 text-xs font-semibold">
              {!x.completado_en ? <button className="text-turquesa-700 hover:underline" onClick={() => accion(() => api.post(`/afore/plazos/${x.id}`, { accion: "completar" }), "Marcado como hecho.")}>Marcar hecho</button>
                : <button className="text-slate-600 hover:underline" onClick={() => accion(() => api.post(`/afore/plazos/${x.id}`, { accion: "reabrir" }))}>Reabrir</button>}
              {x.tipo !== "legal_confirmado" && <button className="text-red-700 hover:underline" onClick={() => {
                const fuente = prompt("Fuente del plazo legal (ley, artículo u oficio):", x.fuente || ""); if (fuente) accion(() => api.post(`/afore/plazos/${x.id}`, { accion: "confirmar_legal", fuente }), "Plazo legal confirmado."); }}>Confirmar como plazo legal</button>}
            </div>}
          </div>))}
        {editor && (
          <form className="tarjeta space-y-2 p-4" onSubmit={(e) => { e.preventDefault();
            accion(() => api.post(`/afore/casos/${id}/plazos`, { ...p, fuente: p.fuente || null, regla: p.regla || null }), "Fecha registrada.").then((r: any) => r && setP({ tipo: "seguimiento_interno", descripcion: "", fecha: "", fuente: "", regla: "" })); }}>
            {cat.reglas_plazo.length > 0 && <div className="flex flex-wrap gap-1.5 text-xs">Sugerir con regla del despacho:
              {cat.reglas_plazo.map((r: any) => <button type="button" key={r.nombre} className="rounded-full border border-crema-300 px-2 py-0.5 hover:bg-crema" onClick={() => sugerir(r)}>{r.nombre} (+{r.dias} d)</button>)}</div>}
            <select className="campo" value={p.tipo} onChange={(e) => setP({ ...p, tipo: e.target.value })}>{Object.entries(cat.tipos_plazo).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select>
            <input className="campo" required minLength={2} maxLength={300} placeholder="Descripción" value={p.descripcion} onChange={(e) => setP({ ...p, descripcion: e.target.value })} />
            <input className="campo" type="date" required value={p.fecha} onChange={(e) => setP({ ...p, fecha: e.target.value })} />
            <input className="campo" maxLength={300} placeholder={p.tipo === "legal_confirmado" ? "Fuente (obligatoria)" : "Fuente (opcional)"} required={p.tipo === "legal_confirmado"} value={p.fuente} onChange={(e) => setP({ ...p, fuente: e.target.value })} />
            <button className="btn-turquesa w-full">Agregar fecha</button>
          </form>
        )}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ Revisión

function Revision({ id }: any) {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`/afore/casos/${id}/revision`).then(setR).catch((e) => setError(e.message)); }, [id]);
  if (!r) return <><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Revisando…</p>}</>;
  const Lista = ({ titulo, items, color }: any) => (
    <section className="tarjeta p-4">
      <h3 className="font-semibold text-marino">{titulo} <span className="text-sm text-slate-400">({items.length})</span></h3>
      {items.length === 0 ? <p className="mt-1 text-sm text-emerald-700">✓ Nada pendiente.</p> : <ul className={`mt-2 list-disc space-y-1 pl-5 text-sm ${color}`}>{items.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>}
    </section>
  );
  return (
    <div className="space-y-4">
      <section className="tarjeta p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-lg font-bold text-marino">{r.listo_para_avanzar ? "Sin pendientes detectados" : "Hay elementos por completar o revisar"}</h2>
            <p className="text-sm text-slate-500">Lista de revisión, no una conclusión: Nomira no valida documentos ni determina derechos.</p></div>
          <div className="min-w-[14rem]">
            <div className="flex justify-between text-sm"><span>Documentos recibidos</span><b>{r.progreso.recibidos} de {r.progreso.total} ({r.progreso.porcentaje_recibidos}%)</b></div>
            <div className="mt-1 h-2 rounded-full bg-crema-300"><div className="h-2 rounded-full bg-turquesa" style={{ width: `${r.progreso.porcentaje_recibidos}%` }} /></div>
            <p className="mt-1 text-[11px] text-slate-500">{r.progreso.explicacion}</p>
          </div>
        </div>
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Lista titulo="Datos por confirmar" items={r.faltan_datos} color="text-amber-800" />
        <Lista titulo="Documentos que faltan" items={r.faltan_documentos} color="text-amber-800" />
        <Lista titulo="Posibles inconsistencias" items={r.inconsistencias} color="text-red-800" />
        <Lista titulo="Folios o acuses no registrados" items={r.folios_pendientes} color="text-amber-800" />
        <Lista titulo="Requiere revisión de un abogado" items={r.revision_abogado} color="text-slate-700" />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Portal y mensajes

function Portal({ d, c, id, cat, editor, accion }: any) {
  const [f, setF] = useState({ portal_visible: c.portal_visible, estado_publico: c.estado_publico || "", siguiente_paso_publico: c.siguiente_paso_publico || "", notificar: false });
  const [plantilla, setPlantilla] = useState("actualizacion_portal");
  const [canal, setCanal] = useState("");
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <section className="tarjeta space-y-3 p-5">
        <h2 className="font-semibold text-marino">Lo que ve el cliente en su portal</h2>
        <p className="text-sm text-slate-500">El cliente solo ve lo que usted escriba aquí, los documentos del checklist marcados como visibles y los documentos que usted comparta. Nunca notas internas ni análisis.</p>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!editor} checked={f.portal_visible} onChange={(e) => setF({ ...f, portal_visible: e.target.checked })} /> Mostrar este caso en el portal del cliente</label>
        <label className="block"><span className="etiqueta">Estado general (en palabras sencillas)</span><textarea className="campo" rows={2} maxLength={500} disabled={!editor} value={f.estado_publico} onChange={(e) => setF({ ...f, estado_publico: e.target.value })} placeholder="p. ej. Estamos reuniendo su documentación" /></label>
        <label className="block"><span className="etiqueta">Siguiente paso que decide compartir</span><textarea className="campo" rows={2} maxLength={500} disabled={!editor} value={f.siguiente_paso_publico} onChange={(e) => setF({ ...f, siguiente_paso_publico: e.target.value })} /></label>
        {editor && <>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.notificar} onChange={(e) => setF({ ...f, notificar: e.target.checked })} /> Preparar un aviso al cliente (quedará esperando su aprobación)</label>
          <button className="btn-primario" onClick={() => accion(() => api.post(`/afore/casos/${id}/publicar`, f), "Portal actualizado.")}>Guardar</button></>}
        {c.publico_actualizado_en && <p className="text-xs text-slate-500">Última actualización compartida: {fechaHora(c.publico_actualizado_en)}</p>}
        <p className="text-xs text-slate-500">El enlace de acceso al portal se genera desde la <Link className="font-semibold text-turquesa-700 hover:underline" href={`/afore/clientes/${c.cliente_id}`}>ficha del cliente</Link>.</p>
      </section>
      <section className="space-y-3">
        <h2 className="font-semibold text-marino">Mensajes de este caso</h2>
        {editor && (
          <div className="tarjeta flex flex-wrap items-end gap-2 p-3">
            <label className="block grow"><span className="etiqueta">Plantilla</span><select className="campo" value={plantilla} onChange={(e) => setPlantilla(e.target.value)}>
              <option value="solicitud_recibida">Confirmar solicitud recibida</option><option value="falta_documentacion">Falta documentación</option>
              <option value="documento_recibido">Documento recibido</option><option value="respuesta_registrada">Respuesta o movimiento registrado</option>
              <option value="actualizacion_portal">Actualización en el portal</option><option value="recordatorio">Recordatorio</option></select></label>
            <label className="block"><span className="etiqueta">Canal</span><select className="campo" value={canal} onChange={(e) => setCanal(e.target.value)}>
              <option value="">Preferido del cliente</option><option value="whatsapp">WhatsApp</option><option value="correo">Correo</option></select></label>
            <button className="btn-turquesa" onClick={() => accion(() => api.post(`/afore/casos/${id}/mensajes`, { plantilla, canal: canal || null }), "Mensaje preparado.")}>Preparar mensaje</button>
          </div>)}
        {d.mensajes.length === 0 && <div className="tarjeta p-6 text-center text-sm text-slate-500">Sin mensajes.</div>}
        {d.mensajes.map((x: any) => <TarjetaMensaje key={x.id} x={x} puedeAprobar={d.puede_aprobar} editor={editor} accion={accion} />)}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ AFORE y CURP

function LocalizarCurp({ d, id, cat, editor, accion }: any) {
  const [finalidad, setFinalidad] = useState("Integrar el expediente del caso");
  const [consiente, setConsiente] = useState(false);
  const [res, setRes] = useState<any>(null);
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="tarjeta space-y-3 p-5">
        <h2 className="font-semibold text-marino">Localizar la AFORE del titular</h2>
        <p className="text-sm text-slate-600">Nomira no consulta AforeWeb por usted ni guarda contraseñas: la consulta la hace el titular en el sitio oficial de la CONSAR (Comisión Nacional del Sistema de Ahorro para el Retiro), y el resultado le llega <b>a su propio correo</b>.</p>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li>Abra (o pida al cliente que abra) el sitio oficial AforeWeb, sección «Localiza tu AFORE».</li>
          <li>El cliente necesita su NSS (si cotizó en el IMSS) o su CURP (si cotizó en el ISSSTE) y un correo electrónico.</li>
          <li>El cliente sube el correo o la captura con el resultado en su portal seguro. También puede llamar a SARTEL al 55 1328 5000.</li>
        </ol>
        <div className="flex flex-wrap gap-2">
          <a className="btn-sec" href={cat.aforeweb} target="_blank" rel="noopener noreferrer">Abrir AforeWeb (sitio oficial) ↗</a>
          {editor && <button className="btn-turquesa" onClick={() => accion(() => api.post(`/afore/casos/${id}/localizacion`, {}), "Consulta registrada y agregada al checklist del cliente.")}>Registrar que se indicó la consulta</button>}
        </div>
        <p className="text-xs text-slate-500">Al registrarla se guarda quién y cuándo, y se pide al cliente en su portal el documento con el resultado.</p>
      </section>
      <section className="tarjeta space-y-3 p-5">
        <h2 className="font-semibold text-marino">CURP: revisión y validación oficial</h2>
        <p className="text-sm text-slate-600">La ficha del cliente revisa el formato y el dígito verificador <b>localmente</b>. Eso no es una consulta oficial.</p>
        {d.curp_oficial.disponible ? <Aviso tipo="ok">Validación oficial disponible para su organización.</Aviso> : <Aviso tipo="alerta">{d.curp_oficial.motivo} Puede continuar con revisión manual.</Aviso>}
        {editor && d.cliente.tiene_curp && (
          <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); const r = await accion(() => api.post(`/afore/casos/${id}/curp-oficial`, { finalidad, consentimiento: consiente })); if (r && r !== true) setRes(r); }}>
            <label className="block"><span className="etiqueta">Finalidad de la consulta</span><input className="campo" required minLength={5} maxLength={300} value={finalidad} onChange={(e) => setFinalidad(e.target.value)} /></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5" checked={consiente} onChange={(e) => setConsiente(e.target.checked)} /> La persona autorizó consultar su CURP para esta finalidad.</label>
            <button className="btn-primario" disabled={!consiente}>{d.curp_oficial.disponible ? "Consultar en el servicio oficial" : "Registrar intento (sin consulta oficial)"}</button>
          </form>
        )}
        {res && (res.oficial ? <Aviso tipo="ok">Respuesta oficial: {res.estatus}</Aviso>
          : <Aviso tipo="info">{res.mensaje}{res.revision_local && <> Revisión local: {res.revision_local.detalle}</>}</Aviso>)}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ Evidencia (opcional)

function Evidencia({ id, editor, accion }: any) {
  const [e, setE] = useState<any>(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.get(`/afore/casos/${id}/evidencia`).then(setE).catch((x) => setError(x.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  if (!e) return <><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</>;
  const vincular = (body: any) => accion(() => api.post(`/afore/casos/${id}/evidencia`, body), "Vinculado.").then(cargar);
  return (
    <div className="space-y-4">
      <Aviso tipo="info">Vincule documentos u hechos revisados de Nomira Evidencia. No se copian archivos y se respeta la visibilidad de cada documento.</Aviso>
      <section className="tarjeta p-4">
        <h2 className="font-semibold text-marino">Vinculados</h2>
        {e.vinculos.length === 0 ? <p className="text-sm text-slate-500">Ninguno.</p> : <ul className="mt-2 space-y-1 text-sm">{e.vinculos.map((v: any) => (
          <li key={v.id} className="flex justify-between gap-2"><span>{v.hecho ? <>{v.hecho_fecha && <b>{fecha(v.hecho_fecha)} · </b>}{v.hecho}</> : v.documento}
            <Link className="ml-2 text-xs text-turquesa-700 hover:underline" href={`/evidencia/${v.asunto_id}`}>abrir asunto ↗</Link></span>
            {editor && <button className="text-xs text-red-700 hover:underline" onClick={() => accion(() => api.borrar(`/afore/evidencia/${v.id}`), "Quitado.").then(cargar)}>Quitar</button>}</li>))}</ul>}
      </section>
      {editor && e.opciones.map((a: any) => (
        <details key={a.asunto_id} className="tarjeta p-4"><summary className="cursor-pointer font-semibold text-marino">{a.asunto}</summary>
          <div className="mt-2 grid gap-3 md:grid-cols-2 text-sm">
            <div><div className="etiqueta">Documentos</div>{a.documentos.map((x: any) => <button key={x.id} className="block text-left text-turquesa-700 hover:underline" onClick={() => vincular({ ev_documento_id: x.id })}>+ {x.nombre}</button>)}</div>
            <div><div className="etiqueta">Hechos revisados</div>{a.hechos.map((x: any) => <button key={x.id} className="block text-left text-turquesa-700 hover:underline" onClick={() => vincular({ ev_hecho_id: x.id })}>+ {x.fecha && `${fecha(x.fecha)} · `}{x.descripcion}</button>)}</div>
          </div></details>))}
    </div>
  );
}

function Historial({ id }: any) {
  const [h, setH] = useState<any[] | null>(null);
  useEffect(() => { api.get(`/afore/casos/${id}/historial`).then(setH).catch(() => setH([])); }, [id]);
  const NOMBRES: Record<string, string> = { af_caso_creado: "Creó el caso", af_caso_modificado: "Modificó el caso", af_requisito_modificado: "Actualizó el checklist", af_requisito_agregado: "Agregó al checklist",
    af_documento_cargado: "Cargó un documento", af_documento_recibido_cliente: "El cliente envió un documento", af_documento_modificado: "Revisó un documento", af_documento_descargado: "Descargó un documento",
    af_actividad_registrada: "Registró una actividad", af_actividad_modificada: "Modificó una actividad", af_plazo_registrado: "Registró una fecha", af_mensaje_aprobar: "Aprobó un mensaje",
    af_mensaje_creado: "Preparó un mensaje", af_mensaje_cancelar: "Canceló un mensaje", af_portal_actualizado: "Actualizó lo que ve el cliente", af_localizacion_registrada: "Registró la consulta de AFORE",
    af_consulta_curp: "Intentó consulta oficial de CURP", af_evidencia_vinculada: "Vinculó evidencia" };
  if (!h) return <p className="text-sm text-slate-500">Cargando…</p>;
  return (
    <div className="tarjeta overflow-x-auto">
      <table className="tabla"><thead><tr><th>Fecha</th><th>Quién</th><th>Qué</th></tr></thead>
        <tbody>{h.map((x, i) => <tr key={i}><td className="whitespace-nowrap">{fechaHora(x.fecha)}</td><td>{x.usuario}</td><td>{NOMBRES[x.accion] || x.accion}
          {x.detalle?.antes && x.detalle?.despues && <span className="text-xs text-slate-500"> ({x.detalle.antes} → {x.detalle.despues})</span>}</td></tr>)}</tbody></table>
    </div>
  );
}
