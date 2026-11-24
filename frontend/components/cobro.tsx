"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api, mxn } from "@/lib/api";

const ESTADO_LIGA: Record<string, [string, string]> = {
  pendiente: ["Esperando pago", "bg-amber-100 text-amber-800"], pagada: ["Pagada", "bg-emerald-100 text-emerald-800"],
  vencida: ["Vencida", "bg-slate-100 text-slate-500"], cancelada: ["Desactivada", "bg-slate-100 text-slate-500"],
};
const ESTADO_FACTURA: Record<string, [string, string]> = {
  valida: ["Vigente", "bg-emerald-100 text-emerald-800"], en_cancelacion: ["En cancelación", "bg-amber-100 text-amber-800"],
  cancelada: ["Cancelada", "bg-slate-100 text-slate-500"],
};
const fecha = (s: string) => new Date(s).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" });

/** Tarjeta de la ficha del cliente: ligas de pago (Stripe del despacho) y facturas CFDI (Facturapi del despacho). */
export function CobroCliente({ c, onCambio }: { c: any; onCambio: () => void }) {
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [dialogo, setDialogo] = useState<"" | "liga" | "factura" | "cancelar">("");
  const [pago, setPago] = useState<any>(null);
  const [factura, setFactura] = useState<any>(null);
  const cargar = useCallback(() => api.get(`/cobro/clientes/${c.id}`).then((r) => {
    setD(r);
    if (r.pagos_nuevos) { setOk(`Se confirmó ${r.pagos_nuevos === 1 ? "un pago en línea" : `${r.pagos_nuevos} pagos en línea`} y se registró en la cuenta.`); onCambio(); }
  }).catch((e) => setError(e.message)), [c.id, onCambio]);
  useEffect(() => { cargar(); }, [cargar]);
  async function accion(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await f(); setOk(msg); await cargar(); } catch (e: any) { setError(e.message); }
  }
  async function descargar(f: any, formato: "pdf" | "xml") {
    try {
      const { blob, nombre } = await api.blob(`/cobro/facturas/${f.id}/${formato}`);
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = nombre || `factura.${formato}`; a.click();
    } catch (e: any) { setError(e.message); }
  }
  async function copiar(url: string) {
    try { await navigator.clipboard.writeText(url); setOk("Liga copiada. Pégala en WhatsApp o en un correo para tu cliente."); } catch { setError("No se pudo copiar. Selecciona la liga y cópiala."); }
  }
  if (!d) return error ? <Aviso>{error}</Aviso> : null;
  const conFactura = new Set(d.facturas.filter((f: any) => f.estado !== "cancelada").map((f: any) => f.pago_id));
  const porFacturar = c.pagos.filter((p: any) => !p.cancelado && !conFactura.has(p.id));
  const nada = !d.stripe && !d.facturapi;
  return (
    <section className="tarjeta overflow-hidden" aria-label="Cobro en línea y facturas">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-4 py-3">
        <h2 className="font-semibold text-marino">Cobro en línea y facturas</h2>
        <div className="flex flex-wrap gap-2">
          {c.puede_editar && d.stripe && Number(c.cuenta.saldo) > 0 && <button className="btn-turquesa" onClick={() => setDialogo("liga")}>Crear liga de pago</button>}
          <Link href="/clientes/cobro" className="btn-sec text-sm">Configurar</Link>
        </div>
      </div>
      <div className="space-y-2 px-4 pt-3"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {nada ? <p className="p-4 text-sm text-slate-600">Conecta tu cuenta de <b>Stripe</b> para mandar ligas de pago (tarjeta, OXXO o transferencia, según lo que tengas activo) y tu cuenta de <b>Facturapi</b> para timbrar facturas CFDI 4.0 desde aquí. Se configura una sola vez en <Link href="/clientes/cobro" className="font-semibold text-turquesa-700 underline">Cobro y facturación</Link>.</p> : <>
        {(d.stripe_prueba || d.facturapi_prueba) && <p className="mx-4 mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">Modo de prueba: {[d.stripe_prueba && "las ligas no cobran dinero real", d.facturapi_prueba && "las facturas no tienen validez ante el SAT"].filter(Boolean).join(" y ")}.</p>}
        {d.stripe && <div className="p-4">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">Ligas de pago</h3>
          {d.ligas.length ? <ul className="mt-1 divide-y divide-crema-200 text-sm">{d.ligas.map((x: any) => (
            <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span><b className="text-marino">{mxn(x.monto)}</b> · {x.concepto} · <span className="text-slate-500">{fecha(x.creado_en)}</span>{" "}
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_LIGA[x.estado][1]}`}>{ESTADO_LIGA[x.estado][0]}</span></span>
              {x.estado === "pendiente" && <span className="flex flex-wrap gap-3 text-xs">
                <button className="font-semibold text-turquesa-700 underline" onClick={() => copiar(x.url)}>Copiar liga</button>
                <a className="font-semibold text-turquesa-700 underline" target="_blank" rel="noopener noreferrer"
                  href={`https://wa.me/?text=${encodeURIComponent(`Hola, te comparto la liga para pagar ${x.concepto} (${mxn(x.monto)}): ${x.url}`)}`}>Mandar por WhatsApp</a>
                <button className="text-slate-500 underline" onClick={() => accion(() => api.post(`/cobro/ligas/${x.id}/cancelar`), "Liga desactivada.")}>Desactivar</button>
                <button className="text-slate-500 underline" onClick={() => accion(() => cargar(), "Revisado en Stripe.")}>¿Ya pagó?</button></span>}
            </li>))}</ul> : <p className="mt-1 text-sm text-slate-500">Crea una liga por lo pendiente y mándala a tu cliente. Cuando pague, el pago se registra solo en esta cuenta.</p>}
        </div>}
        {d.facturapi && <div className="border-t border-crema-200 p-4">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">Facturas (CFDI 4.0)</h3>
          {d.faltantes_factura.length > 0 && <p className="mt-1 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">Para facturar falta: {d.faltantes_factura.join(", ")}.</p>}
          {d.facturas.length > 0 && <ul className="mt-1 divide-y divide-crema-200 text-sm">{d.facturas.map((f: any) => (
            <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span><b className="text-marino">{mxn(f.total)}</b> · {f.serie_folio || "Factura"} · <span className="text-slate-500">{fecha(f.creado_en)}</span>{" "}
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_FACTURA[f.estado][1]}`}>{ESTADO_FACTURA[f.estado][0]}</span>
                {f.uuid && <span className="block text-xs text-slate-400">Folio fiscal {f.uuid}</span>}</span>
              <span className="flex flex-wrap gap-3 text-xs">
                <button className="font-semibold text-turquesa-700 underline" onClick={() => descargar(f, "pdf")}>PDF</button>
                <button className="font-semibold text-turquesa-700 underline" onClick={() => descargar(f, "xml")}>XML</button>
                {c.puede_editar && f.estado === "valida" && <button className="font-semibold text-turquesa-700 underline" onClick={() => accion(() => api.post(`/cobro/facturas/${f.id}/enviar`, {}), "Factura enviada al correo del cliente.")}>Enviar por correo</button>}
                {c.es_admin && f.estado === "valida" && <button className="text-slate-500 underline" onClick={() => { setFactura(f); setDialogo("cancelar"); }}>Cancelar</button>}</span>
            </li>))}</ul>}
          {c.puede_editar && porFacturar.length > 0 && d.faltantes_factura.length === 0 && <ul className="mt-2 space-y-1 text-sm">{porFacturar.map((p: any) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-crema/50 px-3 py-2">
              <span>Pago {mxn(p.monto)} · folio {p.folio} · {p.metodo_texto}</span>
              <button className="btn-sec text-sm" onClick={() => { setPago(p); setDialogo("factura"); }}>Facturar este pago</button></li>))}</ul>}
          {!d.facturas.length && !porFacturar.length && <p className="mt-1 text-sm text-slate-500">Cuando registres un pago podrás timbrar su factura aquí.</p>}
        </div>}
      </>}
      {dialogo === "liga" && <FormLiga c={c} onCerrar={() => setDialogo("")} onListo={(x) => { setDialogo(""); setOk("Liga creada. Cópiala o mándala por WhatsApp."); cargar(); copiar(x.url); }} />}
      {dialogo === "factura" && pago && <FormFactura pago={pago} usos={d.usos} uso={d.uso_cfdi} onCerrar={() => setDialogo("")}
        onListo={() => { setDialogo(""); setOk("Factura timbrada."); cargar(); }} />}
      {dialogo === "cancelar" && factura && <Modal titulo="Cancelar factura ante el SAT" onCerrar={() => setDialogo("")}>
        <CancelarFactura motivos={d.motivos_cancelacion} onCerrar={() => setDialogo("")} onConfirmar={(motivo) => {
          setDialogo(""); accion(() => api.post(`/cobro/facturas/${factura.id}/cancelar`, { motivo }), "Cancelación enviada al SAT.");
        }} /></Modal>}
    </section>
  );
}

function FormLiga({ c, onCerrar, onListo }: { c: any; onCerrar: () => void; onListo: (x: any) => void }) {
  const pendientes = c.cargos.filter((g: any) => Number(g.pendiente) > 0 && g.estado !== "cancelado");
  const [cargo, setCargo] = useState<string>(pendientes[0] ? String(pendientes[0].id) : "");
  const elegido = pendientes.find((g: any) => String(g.id) === cargo);
  const [monto, setMonto] = useState<string>(elegido ? elegido.pendiente : c.cuenta.saldo);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function crear(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { onListo(await api.post(`/cobro/clientes/${c.id}/ligas`, { cargo_id: cargo ? Number(cargo) : null, monto })); }
    catch (er: any) { setError(er.message); } finally { setEnviando(false); }
  }
  return (
    <Modal titulo="Crear liga de pago" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={crear}>
        <label className="block"><span className="etiqueta">¿Qué va a pagar?</span>
          <select className="campo" value={cargo} onChange={(e) => { setCargo(e.target.value); const g = pendientes.find((x: any) => String(x.id) === e.target.value); setMonto(g ? g.pendiente : c.cuenta.saldo); }}>
            {pendientes.map((g: any) => <option key={g.id} value={g.id}>{g.concepto} — pendiente {mxn(g.pendiente)}</option>)}
            <option value="">Todo el saldo — {mxn(c.cuenta.saldo)}</option>
          </select></label>
        <label className="block"><span className="etiqueta">Monto a cobrar (puede ser una parte)</span>
          <input className="campo" inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} required /></label>
        <p className="text-xs text-slate-500">Tu cliente paga en la página segura de Stripe con los medios que tengas activos en tu cuenta. Nomira no ve ni guarda datos de tarjeta. La liga vence en 24 horas.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={enviando}>{enviando ? "Creando…" : "Crear liga"}</button></div>
      </form>
    </Modal>
  );
}

function FormFactura({ pago, usos, uso, onCerrar, onListo }: { pago: any; usos: Record<string, string>; uso: string; onCerrar: () => void; onListo: () => void }) {
  const [u, setU] = useState(uso);
  const [concepto, setConcepto] = useState(`Servicios profesionales jurídicos${pago.concepto && pago.concepto !== "A cuenta" ? `: ${pago.concepto}` : ""}`);
  const [desglose, setDesglose] = useState<any>(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { api.get(`/cobro/pagos/${pago.id}/desglose`).then(setDesglose).catch(() => {}); }, [pago.id]);
  async function timbrar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { await api.post(`/cobro/pagos/${pago.id}/factura`, { uso: u, concepto }); onListo(); }
    catch (er: any) { setError(er.message); } finally { setEnviando(false); }
  }
  return (
    <Modal titulo={`Facturar pago de ${mxn(pago.monto)}`} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={timbrar}>
        <label className="block"><span className="etiqueta">Concepto</span><input className="campo" value={concepto} onChange={(e) => setConcepto(e.target.value)} maxLength={1000} required /></label>
        <label className="block"><span className="etiqueta">Uso del CFDI</span>
          <select className="campo" value={u} onChange={(e) => setU(e.target.value)}>{Object.entries(usos).map(([k, v]) => <option key={k} value={k}>{k} · {v}</option>)}</select></label>
        {desglose && <dl className="grid grid-cols-2 gap-1 rounded-lg bg-crema/50 p-3 text-sm">
          <dt className="text-slate-500">Subtotal</dt><dd className="text-right">{mxn(desglose.subtotal)}</dd>
          <dt className="text-slate-500">IVA 16 %</dt><dd className="text-right">{mxn(desglose.iva)}</dd>
          {Number(desglose.ret_isr) > 0 && <><dt className="text-slate-500">Retención ISR</dt><dd className="text-right">−{mxn(desglose.ret_isr)}</dd></>}
          {Number(desglose.ret_iva) > 0 && <><dt className="text-slate-500">Retención IVA</dt><dd className="text-right">−{mxn(desglose.ret_iva)}</dd></>}
          <dt className="font-semibold text-marino">Total</dt><dd className="text-right font-semibold text-marino">{mxn(desglose.total)}</dd></dl>}
        <p className="text-xs text-slate-500">Se timbra como pago en una sola exhibición (PUE), con la forma de pago que registraste. Revisa los datos con tu contador.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={enviando}>{enviando ? "Timbrando…" : "Timbrar factura"}</button></div>
      </form>
    </Modal>
  );
}

function CancelarFactura({ motivos, onCerrar, onConfirmar }: { motivos: Record<string, string>; onCerrar: () => void; onConfirmar: (m: string) => void }) {
  const [m, setM] = useState("02");
  return (
    <div className="space-y-3">
      <label className="block"><span className="etiqueta">Motivo (catálogo del SAT)</span>
        <select className="campo" value={m} onChange={(e) => setM(e.target.value)}>{Object.entries(motivos).map(([k, v]) => <option key={k} value={k}>{k} · {v}</option>)}</select></label>
      <p className="text-sm text-slate-600">La cancelación se envía al SAT y no se puede deshacer. En algunos casos tu cliente tiene que aceptarla desde su buzón tributario.</p>
      <div className="flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>No cancelar</button>
        <button className="btn-turquesa bg-red-700" onClick={() => onConfirmar(m)}>Cancelar factura</button></div>
    </div>
  );
}
