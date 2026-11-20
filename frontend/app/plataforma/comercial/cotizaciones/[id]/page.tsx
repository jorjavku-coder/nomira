"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ComercialShell, Constructor, Desglose, EstadoCot, abrirPdf, useCatalogoCM } from "@/components/comercial";
import { Aviso, Modal } from "@/components/ui";
import { fecha, fechaHora, mxn } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

const ACTOR: Record<string, string> = { admin: "", cliente: "Cliente", stripe: "Stripe (prueba)", sistema: "Sistema" };
const METODO: Record<string, string> = { spei: "Transferencia SPEI", otro: "Otra forma", tarjeta: "Tarjeta" };

export default function Cotizacion() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [cat] = useCatalogoCM();
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [editar, setEditar] = useState(false);
  const [dialogo, setDialogo] = useState<string | null>(null);
  const cargar = useCallback(() => apiP.get(`/comercial/cotizaciones/${id}`).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(fn: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { const r = await fn(); if (r?.folio) setC(r); setOk(msg); return r; } catch (e: any) { setError(e.message); return null; }
  }
  if (!c) return <ComercialShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</ComercialShell>;
  const a = c.acciones;
  const v = c.version;
  return (
    <ComercialShell>
      <Link href="/plataforma/comercial/cotizaciones" className="text-sm text-turquesa-700 hover:underline">← Cotizaciones</Link>
      <div className="mb-4 mt-1 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex flex-wrap items-center gap-3 text-3xl font-extrabold text-marino">{c.folio} <EstadoCot estado={c.estado} texto={c.estado_texto} /></h1>
          <p className="mt-1 text-sm text-slate-500">{c.despacho} · {c.contacto} · {c.email} · versión {c.version_actual}
            {c.version_enviada && c.version_enviada !== c.version_actual ? ` (el cliente ve la versión ${c.version_enviada})` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {a.editar && !editar && <button className="btn-sec" onClick={() => setEditar(true)}>{a.editar_crea_version ? "Editar (nueva versión)" : "Editar borrador"}</button>}
          {a.marcar_revision && <button className="btn-sec" onClick={() => hacer(() => apiP.post(`/comercial/cotizaciones/${id}/estado`, { estado: "revision" }), "Marcada como lista para revisión.")}>Marcar lista para revisión</button>}
          {a.regresar_borrador && <button className="btn-sec" onClick={() => hacer(() => apiP.post(`/comercial/cotizaciones/${id}/estado`, { estado: "borrador" }), "Regresó a borrador.")}>Regresar a borrador</button>}
          <button className="btn-sec" onClick={() => abrirPdf(`/comercial/cotizaciones/${id}/pdf`, `${c.folio}-v${c.version_actual}.pdf`, true).catch((e) => setError(e.message))}>Descargar PDF</button>
          <button className="btn-sec" onClick={async () => { const r = await hacer(() => apiP.post(`/comercial/cotizaciones/${id}/duplicar`), "Cotización duplicada."); if (r) router.push(`/plataforma/comercial/cotizaciones/${r.id}`); }}>Duplicar</button>
          {a.cancelar && <button className="btn-peligro" onClick={() => setDialogo("cancelar")}>Cancelar</button>}
        </div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      {editar && cat ? <Constructor cat={cat} cot={c} onCancelar={() => setEditar(false)} onGuardado={(r) => { setC(r); setEditar(false); setOk(c.acciones.editar_crea_version ? `Se creó la versión ${r.version_actual}.` : "Borrador guardado."); }} />
        : <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
          <div className="space-y-5">
            {a.enviar && <RevisionEnvio c={c} cat={cat} onEnviada={(r) => { setC(r); setOk(r.envio?.manual ? "Marcada como enviada por fuera de Nomira." : r.envio?.prueba ? "Enviada en MODO DE PRUEBA: el correo se guardó en el servidor y no salió." : "Cotización enviada."); }} onError={setError} />}
            {c.enlace?.existe && a.enlace && <section className="tarjeta p-5">
              <h2 className="font-semibold text-marino">Enlace seguro del cliente</h2>
              {c.enlace.url ? <>
                <div className="mt-2 flex flex-wrap items-center gap-2"><code className="break-all rounded bg-crema-200 px-2 py-1 text-xs">{c.enlace.url}</code>
                  <button className="btn-sec py-1 text-xs" onClick={() => navigator.clipboard?.writeText(c.enlace.url).then(() => setOk("Enlace copiado."))}>Copiar</button></div>
                <p className="mt-1 text-xs text-slate-500">Vence el {fechaHora(c.enlace.vence_en)}. Después de la vigencia el cliente solo verá el aviso y el contacto comercial.</p>
              </> : <p className="mt-1 text-sm text-slate-600">El enlace está revocado.</p>}
              <div className="mt-3 flex gap-2">
                {c.enlace.url && <button className="btn-sec" onClick={() => hacer(() => apiP.post(`/comercial/cotizaciones/${id}/enlace`, { accion: "revocar" }), "Enlace revocado.")}>Revocar enlace</button>}
                <button className="btn-sec" onClick={() => hacer(() => apiP.post(`/comercial/cotizaciones/${id}/enlace`, { accion: "regenerar" }), "Se generó un enlace nuevo; el anterior dejó de funcionar.")}>Generar enlace nuevo</button>
              </div>
            </section>}
            {(a.registrar_pago || c.pagos.length > 0) && <section className="tarjeta p-5">
              <div className="flex items-center justify-between"><h2 className="font-semibold text-marino">Pagos</h2>
                {a.registrar_pago && <button className="btn-sec" onClick={() => setDialogo("pago")}>Registrar pago recibido</button>}</div>
              <p className="text-xs text-slate-500">Un comprobante del cliente no marca la cotización como pagada: usted confirma la recepción.</p>
              {c.pagos.length ? <ul className="mt-2 divide-y divide-crema-300 text-sm">{c.pagos.map((p: any) => (
                <li key={p.id} className="flex flex-wrap justify-between gap-2 py-2">
                  <span>{METODO[p.metodo]} · {p.referencia || "—"} {p.fecha_pago && `· ${fecha(p.fecha_pago)}`}<span className="block text-xs text-slate-500">{p.estado === "confirmado" ? `Confirmado ${p.registrado_por ? `por ${p.registrado_por}` : "por Stripe"}` : "Iniciado (sin confirmar)"}</span></span>
                  <span className="font-semibold">{mxn(p.monto)}</span></li>))}</ul> : <p className="mt-2 text-sm text-slate-500">Sin pagos registrados.</p>}
              <p className="mt-2 text-sm">Pagado: <b>{mxn(c.pagado)}</b> de {mxn(v.calculo.total)}</p>
            </section>}
            {(a.convertir || a.asignar_promocional || c.asignacion) && <section className="tarjeta p-5">
              <h2 className="font-semibold text-marino">Asignación al despacho</h2>
              {c.asignacion ? <p className="mt-1 text-sm">Asignada a <Link className="font-semibold text-turquesa-700 hover:underline" href={`/plataforma/clientes/${c.asignacion.organizacion_id}`}>{c.asignacion.organizacion}</Link> · {c.asignacion.paquete} · {c.asignacion.usuarios} usuarios · {c.asignacion.almacenamiento_gb} GB · renovación {fecha(c.asignacion.renovacion)} · {c.asignacion.origen === "promocional" ? `promocional (${c.asignacion.motivo})` : "por pago"}</p>
                : <><p className="mt-1 text-sm text-slate-600">{a.convertir ? "El pago está confirmado: asigne el paquete al despacho para activar sus módulos." : "Sin pago confirmado solo se puede hacer una asignación promocional aprobada."}</p>
                  <div className="mt-3 flex gap-2">
                    {a.convertir && <button className="btn-turquesa" onClick={() => setDialogo("convertir")}>Asignar al despacho</button>}
                    {a.asignar_promocional && <button className="btn-sec" onClick={() => setDialogo("promocional")}>Asignación promocional</button>}
                  </div></>}
            </section>}
            <section className="tarjeta p-5">
              <h2 className="font-semibold text-marino">Versiones</h2>
              <ul className="mt-2 divide-y divide-crema-300 text-sm">{c.versiones.map((x: any) => (
                <li key={x.numero} className="py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span><b>Versión {x.numero}</b> · {x.paquete} · {mxn(x.total)} · {x.enviada_en ? `enviada ${fechaHora(x.enviada_en)}` : "sin enviar"}</span>
                    <button className="text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => abrirPdf(`/comercial/cotizaciones/${id}/pdf?version=${x.numero}`, `${c.folio}-v${x.numero}.pdf`).catch((e) => setError(e.message))}>Ver PDF</button>
                  </div>
                  {x.cambios && <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">{x.cambios.map((t: string) => <li key={t}>{t}</li>)}</ul>}
                  {x.huella && <p className="mt-1 break-all font-mono text-[10px] text-slate-400">Huella SHA-256: {x.huella}</p>}
                </li>))}</ul>
            </section>
            <section className="tarjeta p-5">
              <h2 className="font-semibold text-marino">Historial de eventos</h2>
              <ol className="mt-2 space-y-2 text-sm">{c.eventos.map((e: any) => (
                <li key={e.id} className="border-l-2 border-turquesa/40 pl-3">
                  <div className="font-medium text-marino">{e.texto} <span className="text-xs font-normal text-slate-500">· v{e.version} · {fechaHora(e.fecha)} · {e.por || ACTOR[e.actor] || e.actor}</span></div>
                  {e.detalle?.mensaje && <p className="text-slate-600">«{e.detalle.mensaje}»</p>}
                  {e.detalle?.motivo && <p className="text-slate-600">Motivo: {e.detalle.motivo}</p>}
                  {e.tipo === "aceptada" && <p className="text-xs text-slate-600">Registrada por {e.detalle.nombre}{e.detalle.cargo ? ` (${e.detalle.cargo})` : ""} sobre la versión {e.detalle.version}. Huella {String(e.detalle.huella).slice(0, 12)}…</p>}
                  {e.detalle?.cambios && <p className="text-xs text-slate-600">{e.detalle.cambios.join(" · ")}</p>}
                  {e.detalle?.monto && <p className="text-xs text-slate-600">{METODO[e.detalle.metodo] || e.detalle.metodo} · {mxn(e.detalle.monto)} {e.detalle.referencia ? `· ref. ${e.detalle.referencia}` : ""}</p>}
                  {e.detalle?.error && <p className="text-xs text-red-700">{e.detalle.error}</p>}
                </li>))}</ol>
            </section>
          </div>
          <aside className="space-y-5">
            <section className="tarjeta p-5">
              <h2 className="mb-2 font-semibold text-marino">Importe · versión {v.numero}</h2>
              <Desglose calc={v.calculo} />
              <p className="mt-3 text-sm">Vigencia: <b>{fechaHora(c.vence_en)}</b></p>
              {v.calculo.descuento?.motivo && <p className="mt-1 text-xs text-slate-500">Motivo del descuento (interno): {v.calculo.descuento.motivo}</p>}
            </section>
            {c.notas_internas && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><b>Notas internas</b> (nunca las ve el cliente)<p className="mt-1 whitespace-pre-wrap">{c.notas_internas}</p></section>}
          </aside>
        </div>}

      {dialogo === "cancelar" && <Motivo titulo="Cancelar cotización" boton="Cancelar cotización" onCerrar={() => setDialogo(null)}
        onConfirmar={(motivo) => hacer(() => apiP.post(`/comercial/cotizaciones/${id}/cancelar`, { motivo }), "Cotización cancelada.").then((r) => r && setDialogo(null))} />}
      {dialogo === "pago" && <RegistrarPago total={v.calculo.total} pagado={c.pagado} onCerrar={() => setDialogo(null)}
        onGuardar={(d) => hacer(() => apiP.post(`/comercial/cotizaciones/${id}/pagos`, d), "Pago registrado.").then((r) => r && setDialogo(null))} />}
      {(dialogo === "convertir" || dialogo === "promocional") && <Convertir promocional={dialogo === "promocional"} onCerrar={() => setDialogo(null)}
        onGuardar={(d) => hacer(() => apiP.post(`/comercial/cotizaciones/${id}/convertir`, d), "Paquete asignado: módulos activados y periodo registrado.").then((r) => r && setDialogo(null))} />}
    </ComercialShell>
  );
}

function RevisionEnvio({ c, cat, onEnviada, onError }: { c: any; cat: any; onEnviada: (r: any) => void; onError: (m: string) => void }) {
  const [vista, setVista] = useState<any>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [asunto, setAsunto] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState<"correo" | "manual" | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const calc = c.version.calculo;
  const refrescar = useCallback((m?: string | null, s?: string) => apiP.post(`/comercial/cotizaciones/${c.id}/vista-correo`, { mensaje: m || null, asunto: s || null })
    .then((r) => { setVista(r); setMensaje((x) => x ?? r.mensaje); setAsunto((x) => x || r.asunto); }).catch((e) => onError(e.message)), [c.id, onError]);
  useEffect(() => { refrescar(); }, [refrescar, c.version.numero, c.version.calculo.total]);
  useEffect(() => {
    let url: string | null = null;
    apiP.blob(`/comercial/cotizaciones/${c.id}/pdf`).then((b) => { url = URL.createObjectURL(b); setPdfUrl(url); }).catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [c.id, c.version.numero, c.version.calculo.total]);
  const correoOk = vista?.correo.configurado;
  async function enviar(manual: boolean) {
    setEnviando(true);
    try { onEnviada(await apiP.post(`/comercial/cotizaciones/${c.id}/enviar`, { confirmacion: cat?.confirmacion || "Enviar cotización", mensaje, asunto, manual })); }
    catch (e: any) { onError(e.detalle?.mensaje || e.message); }
    finally { setEnviando(false); setConfirmar(null); }
  }
  const formas = cat?.integraciones.formas_pago || [];
  return (
    <section className="tarjeta p-5">
      <h2 className="font-semibold text-marino">Revisión y envío</h2>
      {!correoOk && vista && <div className="mt-2"><Aviso tipo="alerta"><b>El correo no está configurado.</b> No se enviará nada desde Nomira. Puede descargar el PDF y copiar el texto del correo para enviarlo usted, y después marcarla como enviada.</Aviso></div>}
      {correoOk && vista?.correo.prueba && <div className="mt-2"><Aviso tipo="info">Correo en <b>modo de prueba</b>: el mensaje se guardará en el servidor y no saldrá.</Aviso></div>}
      <dl className="mt-3 grid gap-x-4 gap-y-1 rounded-2xl bg-crema p-4 text-sm sm:grid-cols-[10rem_1fr]">
        <dt className="text-slate-500">Paquete</dt><dd>{calc.paquete.nombre} · cobro {calc.periodicidad.nombre.toLowerCase()}</dd>
        <dt className="text-slate-500">Módulos</dt><dd>{calc.modulos.map((m: any) => m.nombre + (m.incluido ? "" : " (adicional)")).join(", ")}</dd>
        <dt className="text-slate-500">Capacidades</dt><dd>{calc.usuarios.total} usuarios internos · {calc.almacenamiento.total_gb} GB</dd>
        <dt className="text-slate-500">Precio</dt><dd>Subtotal {mxn(calc.subtotal)}{calc.descuento ? ` · descuento -${mxn(calc.descuento.importe)}` : ""} · IVA {mxn(calc.iva)} · <b>Total {mxn(calc.total)} MXN</b></dd>
        <dt className="text-slate-500">Vigencia</dt><dd>Hasta {fechaHora(c.vence_en)}</dd>
        <dt className="text-slate-500">Formas de pago</dt><dd>{formas.length ? formas.map((f: any) => f.nombre).join(", ") : <span className="text-amber-800">Ninguna configurada: el PDF dirá que se compartirán al contratar.</span>}</dd>
      </dl>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="etiqueta">Vista previa del PDF</div>
          {pdfUrl ? <iframe title="Vista previa del PDF" src={pdfUrl} className="h-[32rem] w-full rounded-xl border border-crema-300" /> : <p className="text-sm text-slate-500">Generando…</p>}
        </div>
        <div>
          <label className="block"><span className="etiqueta">Asunto</span><input className="campo" maxLength={200} value={asunto} onChange={(e) => setAsunto(e.target.value)} /></label>
          <label className="mt-2 block"><span className="etiqueta">Mensaje de presentación</span>
            <textarea className="campo" rows={4} maxLength={4000} value={mensaje ?? ""} onChange={(e) => setMensaje(e.target.value)} /></label>
          <button className="btn-sec mt-2" onClick={() => refrescar(mensaje, asunto)}>Actualizar vista previa</button>
          <div className="etiqueta mt-3">Vista previa del correo · para {vista?.para}</div>
          {vista && <iframe title="Vista previa del correo" srcDoc={vista.html} sandbox="" className="h-[22rem] w-full rounded-xl border border-crema-300 bg-white" />}
          {!correoOk && vista && <button className="btn-sec mt-2" onClick={() => navigator.clipboard?.writeText(`${vista.asunto}\n\n${vista.texto}`).then(() => setCopiado(true))}>{copiado ? "✓ Texto copiado" : "Copiar texto del correo"}</button>}
        </div>
      </div>
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        {!correoOk && <button className="btn-sec" onClick={() => setConfirmar("manual")}>Ya la envié por fuera: marcar como enviada</button>}
        <button className="btn-turquesa" disabled={!correoOk} onClick={() => setConfirmar("correo")}>Enviar cotización</button>
      </div>
      {confirmar && <Modal titulo={confirmar === "correo" ? "Enviar cotización" : "Marcar como enviada"} onCerrar={() => setConfirmar(null)}>
        <p className="text-sm text-slate-700">{confirmar === "correo"
          ? <>Se enviará la cotización <b>{c.folio}</b> (versión {c.version.numero}) por <b>{mxn(calc.total)} MXN</b> a <b>{c.email}</b>, con el PDF adjunto y el enlace seguro. Esta versión quedará congelada.</>
          : <>Confirma que usted ya envió la cotización <b>{c.folio}</b> por su cuenta. Nomira no mandó ningún correo; quedará registrado así y se generará el enlace seguro del cliente.</>}</p>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setConfirmar(null)}>Volver</button>
          <button className="btn-turquesa" disabled={enviando} onClick={() => enviar(confirmar === "manual")}>{enviando ? "Enviando…" : confirmar === "correo" ? "Enviar cotización" : "Marcar como enviada"}</button></div>
      </Modal>}
    </section>
  );
}

function Motivo({ titulo, boton, onCerrar, onConfirmar }: { titulo: string; boton: string; onCerrar: () => void; onConfirmar: (m: string) => void }) {
  const [m, setM] = useState("");
  return <Modal titulo={titulo} onCerrar={onCerrar}>
    <label className="block"><span className="etiqueta">Motivo</span><textarea className="campo" rows={3} value={m} onChange={(e) => setM(e.target.value)} autoFocus /></label>
    <div className="mt-3 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Volver</button><button className="btn-peligro" disabled={m.trim().length < 3} onClick={() => onConfirmar(m.trim())}>{boton}</button></div>
  </Modal>;
}

function RegistrarPago({ total, pagado, onCerrar, onGuardar }: { total: string; pagado: string; onCerrar: () => void; onGuardar: (d: any) => void }) {
  const hoy = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState({ metodo: "spei", monto: "", fecha_pago: hoy, referencia: "" });
  return <Modal titulo="Registrar pago recibido" onCerrar={onCerrar}>
    <p className="mb-3 text-sm text-slate-600">Registre solo pagos que ya verificó en su cuenta. Total: <b>{mxn(total)}</b> · pagado: {mxn(pagado)}.</p>
    <div className="grid gap-3 sm:grid-cols-2">
      <label><span className="etiqueta">Forma de pago</span><select className="campo" value={f.metodo} onChange={(e) => setF({ ...f, metodo: e.target.value })}>{Object.entries(METODO).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
      <label><span className="etiqueta">Monto (MXN)</span><input className="campo" inputMode="decimal" value={f.monto} onChange={(e) => setF({ ...f, monto: e.target.value })} /></label>
      <label><span className="etiqueta">Fecha de pago</span><input className="campo" type="date" max={hoy} value={f.fecha_pago} onChange={(e) => setF({ ...f, fecha_pago: e.target.value })} /></label>
      <label><span className="etiqueta">Referencia</span><input className="campo" value={f.referencia} onChange={(e) => setF({ ...f, referencia: e.target.value })} /></label>
    </div>
    <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Volver</button>
      <button className="btn-turquesa" disabled={!f.monto || f.referencia.trim().length < 2} onClick={() => onGuardar(f)}>Confirmar recepción</button></div>
  </Modal>;
}

function Convertir({ promocional, onCerrar, onGuardar }: { promocional: boolean; onCerrar: () => void; onGuardar: (d: any) => void }) {
  const [orgs, setOrgs] = useState<any[]>([]);
  const [f, setF] = useState({ organizacion_id: "", inicio: new Date().toISOString().slice(0, 10), motivo: "", confirmo: false });
  useEffect(() => { apiP.get("/clientes").then(setOrgs).catch(() => {}); }, []);
  return <Modal titulo={promocional ? "Asignación promocional" : "Asignar paquete al despacho"} onCerrar={onCerrar}>
    <div className="space-y-3">
      <label className="block"><span className="etiqueta">Despacho (organización)</span><select className="campo" value={f.organizacion_id} onChange={(e) => setF({ ...f, organizacion_id: e.target.value })}>
        <option value="">Elija…</option>{orgs.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select></label>
      <p className="text-xs text-slate-500">¿No aparece? Dé de alta al despacho en <Link className="underline" href="/plataforma/clientes">Clientes</Link> y vuelva aquí.</p>
      <label className="block"><span className="etiqueta">Fecha de inicio</span><input className="campo" type="date" value={f.inicio} onChange={(e) => setF({ ...f, inicio: e.target.value })} /></label>
      {promocional && <>
        <label className="block"><span className="etiqueta">Motivo y quién lo aprobó</span><textarea className="campo" rows={2} value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} /></label>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={f.confirmo} onChange={(e) => setF({ ...f, confirmo: e.target.checked })} />
          Confirmo que esta asignación sin pago está aprobada.</label></>}
      <p className="text-xs text-slate-500">Se activan los módulos de la cotización (sin desactivar los que ya tenga), se registra la capacidad contratada y se crea el periodo de suscripción.</p>
    </div>
    <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Volver</button>
      <button className="btn-turquesa" disabled={!f.organizacion_id || (promocional && (!f.confirmo || f.motivo.trim().length < 5))}
        onClick={() => onGuardar({ organizacion_id: Number(f.organizacion_id), inicio: f.inicio, promocional, motivo: f.motivo || null, confirmo: f.confirmo })}>Asignar</button></div>
  </Modal>;
}
