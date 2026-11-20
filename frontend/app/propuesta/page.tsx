"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import { fecha, fechaHora, mxn } from "@/lib/api";

/** Propuesta comercial para el prospecto. El enlace llega como /propuesta#token: el fragmento no
 *  viaja al servidor; aquí se guarda en la pestaña y se manda en el encabezado X-Enlace. El cliente
 *  solo VE la versión enviada: no puede cambiar precios ni módulos. */
const CLAVE = "nomira_propuesta";

async function llamar(ruta: string, token: string, cuerpo?: unknown) {
  const r = await fetch(`/api/propuesta${ruta}`, { method: "POST", headers: { "X-Enlace": token, "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo ?? {}), cache: "no-store" });
  let d: any = null;
  try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error(typeof d?.detail === "string" ? d.detail : "No se pudo completar. Intente de nuevo.");
  return d;
}

export default function Propuesta() {
  const [token, setToken] = useState<string | null>(null);
  const [p, setP] = useState<any>(null);
  const [fatal, setFatal] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [vista, setVista] = useState<"" | "ajustes" | "aceptar">("");
  const [ajuste, setAjuste] = useState("");
  const [acep, setAcep] = useState({ nombre: "", cargo: "", acepto: false });
  const [pago, setPago] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    const h = window.location.hash.slice(1);
    const q = new URLSearchParams(window.location.search);
    if (h) { sessionStorage.setItem(CLAVE, h); history.replaceState(null, "", window.location.pathname); }
    const t = sessionStorage.getItem(CLAVE);
    if (!t) { setFatal("Este enlace no está completo. Pida a Nomira el enlace de su propuesta."); return; }
    setToken(t);
    setPago(q.get("pago"));
    llamar("", t).then(setP).catch((e) => setFatal(e.message === "Este enlace no existe." ? "Este enlace no existe o fue reemplazado por uno nuevo." : e.message));
  }, []);

  async function accion(fn: () => Promise<any>) {
    setError(""); setOk(""); setOcupado(true);
    try { return await fn(); } catch (e: any) { setError(e.message); return null; } finally { setOcupado(false); }
  }
  async function descargar() {
    await accion(async () => {
      const r = await fetch("/api/propuesta/pdf", { method: "POST", headers: { "X-Enlace": token! }, cache: "no-store" });
      if (!r.ok) throw new Error("No se pudo descargar el PDF.");
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a"); a.href = url; a.download = `${p.folio}-v${p.version}.pdf`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    });
  }
  const c = p?.calculo;
  return (
    <main className="min-h-screen bg-crema">
      <header className="bg-marino-900 px-5 py-5"><div className="mx-auto flex max-w-4xl items-center justify-between"><Logo oscuro />
        {p?.folio && <span className="text-right text-sm text-white/80">Propuesta <b className="text-white">{p.folio}</b>{p.version ? ` · versión ${p.version}` : ""}</span>}</div></header>
      <div className="h-1 bg-turquesa" />
      <div className="mx-auto max-w-4xl px-4 py-8">
        {fatal && <div className="tarjeta p-6"><p role="alert" className="text-red-800">{fatal}</p></div>}
        {!fatal && !p && <p className="text-sm text-slate-500">Cargando…</p>}
        {p && !p.disponible && (
          <div className="tarjeta p-8 text-center">
            <h1 className="text-2xl font-extrabold text-marino">{p.mensaje}</h1>
            <p className="mt-2 text-slate-600">{p.motivo === "vencida" ? "Si aún le interesa, con gusto le preparamos una propuesta actualizada." : "Para cualquier duda, comuníquese con el equipo comercial."}</p>
            <Contacto c={p.contacto} />
          </div>)}
        {p?.disponible && c && <>
          {pago === "procesando" && <Nota tipo="info">Estamos esperando la confirmación de su pago con tarjeta. Puede tardar unos minutos; recargue esta página más tarde.</Nota>}
          {pago === "cancelado" && <Nota tipo="alerta">El pago con tarjeta no se completó. Puede intentarlo de nuevo.</Nota>}
          {p.pagada && <Nota tipo="ok"><b>Pago confirmado.</b> Gracias. El equipo de Nomira se pondrá en contacto para activar su cuenta.</Nota>}
          {p.estado === "aceptada" && !p.pagada && <Nota tipo="ok">Registramos su aceptación de la versión {p.version}{p.aceptada_en ? ` el ${fechaHora(p.aceptada_en)}` : ""}.</Nota>}
          {p.estado === "pendiente_pago" && !p.pagada && <Nota tipo="info">Su pago está pendiente de confirmación por parte de Nomira.</Nota>}

          <section className="tarjeta p-6 sm:p-8">
            <p className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">Propuesta para {p.cliente.despacho}</p>
            <h1 className="mt-1 text-3xl font-extrabold text-marino">Paquete {c.paquete.nombre}</h1>
            <p className="mt-1 text-slate-600">Atención: {p.cliente.contacto} · cobro {c.periodicidad.nombre.toLowerCase()}</p>
            <p className="mt-3 inline-block rounded-xl border border-turquesa bg-turquesa-50 px-3 py-1.5 text-sm font-semibold text-marino">Vigencia: hasta el {fechaHora(p.vence_en)}</p>
            {p.necesidad && <p className="mt-4 text-slate-700"><b>Lo que nos compartió:</b> {p.necesidad}</p>}
            <div className="mt-6 grid gap-6 md:grid-cols-2">
              <div>
                <h2 className="font-semibold text-marino">Qué incluye</h2>
                <ul className="mt-2 space-y-1.5 text-sm">
                  {c.modulos.map((m: any) => <li key={m.clave} className="flex justify-between gap-2"><span>✓ {m.nombre}</span><span className="text-slate-500">{m.incluido ? "Incluido" : `Adicional ${mxn(m.unitario)}/mes`}</span></li>)}
                  <li className="flex justify-between gap-2 border-t border-crema-300 pt-1.5"><span>Usuarios internos</span><b>{c.usuarios.total}</b></li>
                  <li className="flex justify-between gap-2"><span>Almacenamiento</span><b>{c.almacenamiento.total_gb} GB</b></li>
                </ul>
                <p className="mt-2 text-xs text-slate-500">Los clientes que invite al portal no cuentan como usuarios internos.
                  {c.asuntos_estimados ? ` Como referencia aproximada, el almacenamiento alcanza para unos ${c.asuntos_estimados.toLocaleString("es-MX")} asuntos; no es un límite.` : ""}</p>
              </div>
              <div>
                <h2 className="font-semibold text-marino">Importe</h2>
                <ul className="mt-2 divide-y divide-crema-300 text-sm">{c.lineas.map((l: any, i: number) => (
                  <li key={i} className="flex justify-between gap-2 py-1.5"><span>{l.concepto}{l.cantidad > 1 ? ` × ${l.cantidad}` : ""}{l.tipo === "unico" ? " (pago único)" : l.meses > 1 ? ` × ${l.meses} meses` : ""}</span><span>{mxn(l.importe)}</span></li>))}</ul>
                <dl className="mt-2 space-y-1 border-t border-crema-300 pt-2 text-sm">
                  <div className="flex justify-between"><dt>Subtotal</dt><dd>{mxn(c.subtotal)}</dd></div>
                  {c.descuento && <div className="flex justify-between text-emerald-700"><dt>Descuento</dt><dd>-{mxn(c.descuento.importe)}</dd></div>}
                  <div className="flex justify-between"><dt>IVA ({Number(c.iva_pct)}%)</dt><dd>{mxn(c.iva)}</dd></div>
                  <div className="flex justify-between rounded-xl bg-turquesa-700 px-3 py-2 text-lg font-bold text-white"><dt>Total MXN</dt><dd>{mxn(c.total)}</dd></div>
                </dl>
              </div>
            </div>
            {[["Condiciones de pago", p.condiciones.condiciones_pago], ["Fecha límite de pago", p.condiciones.fecha_limite_pago && fecha(p.condiciones.fecha_limite_pago)], ["Términos", p.condiciones.terminos],
              ["Observaciones", p.condiciones.observaciones], ["Condiciones comerciales", p.condiciones.generales]].filter(([, v]) => v).length > 0 && (
              <div className="mt-6 space-y-2 text-sm">
                <h2 className="font-semibold text-marino">Condiciones</h2>
                {[["Condiciones de pago", p.condiciones.condiciones_pago], ["Fecha límite de pago", p.condiciones.fecha_limite_pago && fecha(p.condiciones.fecha_limite_pago)], ["Términos", p.condiciones.terminos],
                  ["Observaciones", p.condiciones.observaciones], ["Condiciones comerciales", p.condiciones.generales]].filter(([, v]) => v).map(([t, v]) => (
                  <p key={t as string}><b>{t}:</b> <span className="whitespace-pre-wrap">{v}</span></p>))}
              </div>)}
            <div className="mt-6 flex flex-wrap gap-2">
              <button className="btn-sec" onClick={descargar} disabled={ocupado}>Descargar PDF</button>
              {p.puede_aceptar && <button className="btn-turquesa" onClick={() => setVista("aceptar")}>Aceptar la propuesta</button>}
              {p.puede_pedir_ajustes && <button className="btn-sec" onClick={() => setVista("ajustes")}>Solicitar ajustes</button>}
            </div>
            {error && <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
            {ok && <p role="status" className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{ok}</p>}

            {vista === "ajustes" && <div className="mt-5 rounded-2xl border border-crema-300 p-4">
              <label className="block"><span className="etiqueta">¿Qué le gustaría ajustar?</span><textarea className="campo" rows={3} maxLength={2000} value={ajuste} onChange={(e) => setAjuste(e.target.value)} /></label>
              <div className="mt-2 flex gap-2"><button className="btn-primario" disabled={ajuste.trim().length < 5 || ocupado} onClick={async () => {
                const r = await accion(() => llamar("/ajustes", token!, { mensaje: ajuste.trim() })); if (r) { setOk(r.mensaje); setVista(""); setAjuste(""); }
              }}>Enviar solicitud</button><button className="btn-sec" onClick={() => setVista("")}>Cancelar</button></div>
            </div>}
            {vista === "aceptar" && <div className="mt-5 rounded-2xl border border-turquesa/50 bg-turquesa-50/40 p-4">
              <p className="text-sm text-slate-700">Está por registrar su aceptación de la <b>versión {p.version}</b> de esta propuesta, por <b>{mxn(c.total)} MXN</b>, con las condiciones mostradas arriba
                {" "}y los <Link className="font-semibold text-turquesa-700 underline" href="/legal/terminos" target="_blank">Términos y condiciones de Nomira</Link>.</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label><span className="etiqueta">Su nombre completo</span><input className="campo" value={acep.nombre} onChange={(e) => setAcep({ ...acep, nombre: e.target.value })} /></label>
                <label><span className="etiqueta">Cargo (opcional)</span><input className="campo" value={acep.cargo} onChange={(e) => setAcep({ ...acep, cargo: e.target.value })} /></label>
              </div>
              <label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={acep.acepto} onChange={(e) => setAcep({ ...acep, acepto: e.target.checked })} />
                Revisé la propuesta completa y acepto esta versión en nombre de {p.cliente.despacho}.</label>
              <p className="mt-2 text-xs text-slate-500">Guardaremos la versión aceptada, la fecha, la hora y su nombre.</p>
              <div className="mt-3 flex gap-2"><button className="btn-turquesa" disabled={acep.nombre.trim().length < 3 || !acep.acepto || ocupado} onClick={async () => {
                const r = await accion(() => llamar("/aceptar", token!, { nombre: acep.nombre.trim(), cargo: acep.cargo.trim() || null, version: p.version, acepto: true }));
                if (r) { setP({ ...p, ...r }); setVista(""); setOk("Aceptación registrada. Ahora puede elegir cómo pagar."); }
              }}>Registrar mi aceptación</button><button className="btn-sec" onClick={() => setVista("")}>Cancelar</button></div>
            </div>}
          </section>

          <section className="tarjeta mt-5 p-6">
            <h2 className="font-semibold text-marino">Formas de pago</h2>
            {!p.formas_pago.length && <p className="mt-2 text-sm text-slate-600">Le compartiremos las formas de pago al confirmar su contratación.</p>}
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {p.formas_pago.map((f: any) => (
                <div key={f.clave} className="rounded-2xl border border-crema-300 p-4 text-sm">
                  <div className="font-semibold text-marino">{f.nombre}</div>
                  {f.clave === "spei" && <dl className="mt-1 grid grid-cols-[5rem_1fr] gap-y-0.5"><dt className="text-slate-500">Banco</dt><dd>{f.banco}</dd><dt className="text-slate-500">Titular</dt><dd>{f.titular}</dd>
                    <dt className="text-slate-500">CLABE</dt><dd className="font-mono">{f.clabe}</dd><dt className="text-slate-500">Referencia</dt><dd>{p.folio}</dd></dl>}
                  <p className="mt-1 text-slate-600">{f.instrucciones}</p>
                  {p.puede_pagar && !p.pagada && f.disponible && (f.clave === "tarjeta"
                    ? <button className="btn-turquesa mt-3" disabled={ocupado} onClick={async () => { const r = await accion(() => llamar("/pagar", token!, { metodo: "tarjeta" })); if (r?.url) window.location.href = r.url; }}>Pagar con tarjeta</button>
                    : <button className="btn-sec mt-3" disabled={ocupado} onClick={async () => { const r = await accion(() => llamar("/pagar", token!, { metodo: f.clave })); if (r) { setOk(r.mensaje); setP({ ...p, estado: "pendiente_pago" }); } }}>Pagaré por este medio</button>)}
                </div>))}
            </div>
            {!p.puede_pagar && !p.pagada && p.formas_pago.length > 0 && <p className="mt-2 text-xs text-slate-500">Para pagar, primero registre su aceptación de la propuesta.</p>}
          </section>
          {p.nomira.instrucciones_contratar && <p className="mt-5 text-sm text-slate-600">{p.nomira.instrucciones_contratar}</p>}
          <Contacto c={p.contacto} />
          {p.nomira.notas_pie && <p className="mt-4 text-center text-xs text-slate-500">{p.nomira.notas_pie}</p>}
          <p className="mt-2 text-center text-xs text-slate-400">Esta propuesta no incluye asesoría jurídica. <Link className="underline" href="/legal/privacidad">Aviso de privacidad</Link></p>
        </>}
      </div>
    </main>
  );
}

function Nota({ tipo, children }: { tipo: "ok" | "info" | "alerta"; children: React.ReactNode }) {
  const c = { ok: "border-emerald-200 bg-emerald-50 text-emerald-900", info: "border-marino-100 bg-marino-50 text-marino", alerta: "border-amber-200 bg-amber-50 text-amber-900" }[tipo];
  return <div role="status" className={`mb-4 rounded-2xl border px-4 py-3 text-sm ${c}`}>{children}</div>;
}

function Contacto({ c }: { c: any }) {
  if (!c || !(c.correo || c.telefono || c.sitio_web)) return null;
  return <p className="mt-4 text-center text-sm text-slate-600">Contacto comercial de {c.nombre}: {[c.correo && <a key="c" className="font-semibold text-turquesa-700 underline" href={`mailto:${c.correo}`}>{c.correo}</a>,
    c.telefono && <span key="t">{c.telefono}</span>, c.sitio_web && <span key="s">{c.sitio_web}</span>].filter(Boolean).reduce((a: any[], x, i) => (i ? [...a, " · ", x] : [x]), [])}</p>;
}
