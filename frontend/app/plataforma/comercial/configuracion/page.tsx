"use client";
import { useEffect, useState } from "react";
import { ComercialShell, useCatalogoCM } from "@/components/comercial";
import { Aviso } from "@/components/ui";
import { apiP } from "@/lib/plataforma";

export default function ConfiguracionComercial() {
  const [cat, err] = useCatalogoCM();
  const [f, setF] = useState<any>(null);
  const [integ, setInteg] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  useEffect(() => { if (cat) { setF({ ...cat.config }); setInteg(cat.integraciones); } }, [cat]);
  if (!f) return <ComercialShell><Aviso>{err}</Aviso>{!err && <p className="text-sm text-slate-500">Cargando…</p>}</ComercialShell>;
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const txt = (k: string, t: string, extra: any = {}) => <label className={extra.ancho ? "sm:col-span-2" : ""}><span className="etiqueta">{t}</span>
    {extra.area ? <textarea className="campo" rows={extra.area} value={f[k] || ""} onChange={set(k)} maxLength={extra.max} /> : <input className="campo" value={f[k] || ""} onChange={set(k)} maxLength={extra.max} inputMode={extra.modo} />}</label>;
  async function guardar() {
    setError(""); setOk("");
    try {
      const r = await apiP.put("/comercial/config", { ...f, mb_promedio_por_asunto: f.mb_promedio_por_asunto ? Number(f.mb_promedio_por_asunto) : null, vigencia_dias: Number(f.vigencia_dias) });
      setF({ ...r.config }); setInteg(r.integraciones); setOk("Configuración guardada. Las cotizaciones ya enviadas conservan los datos con los que se enviaron.");
    } catch (e: any) { setError(e.message); }
  }
  const PER: [string, string][] = [["mensual", "Mensual"], ["semestral", "Semestral"], ["anual", "Anual"]];
  return (
    <ComercialShell>
      <h1 className="text-3xl font-extrabold text-marino">Configuración comercial</h1>
      <p className="mb-4 mt-1 text-sm text-slate-500">Lo que deje vacío no aparece en cotizaciones. El logotipo, tipografía y colores son los de Nomira.</p>
      <div className="grid gap-5 xl:grid-cols-2">
        <section className="tarjeta p-5"><h2 className="font-semibold text-marino">Datos de Nomira</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {txt("nombre_comercial", "Nombre comercial")}{txt("razon_social", "Razón social")}{txt("rfc", "RFC", { max: 13 })}{txt("correo_ventas", "Correo de ventas")}
            {txt("telefono", "Teléfono")}{txt("sitio_web", "Sitio web")}{txt("domicilio", "Domicilio", { ancho: true })}
          </div></section>
        <section className="tarjeta p-5"><h2 className="font-semibold text-marino">Impuestos, vigencia y descuentos</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {txt("iva_pct", "IVA general %", { modo: "decimal" })}{txt("vigencia_dias", "Vigencia por defecto (días)", { modo: "numeric" })}
            {txt("descuento_maximo_pct", "Descuento máximo autorizado %", { modo: "decimal" })}{txt("mb_promedio_por_asunto", "MB promedio por asunto (solo referencia; vacío = no estimar)", { modo: "numeric" })}
            <fieldset className="sm:col-span-2"><legend className="etiqueta">Periodicidades habilitadas</legend><div className="flex gap-4 text-sm">
              {PER.map(([k, t]) => <label key={k} className="flex items-center gap-2"><input type="checkbox" className="accent-turquesa" checked={f.periodicidades.includes(k)}
                onChange={(e) => setF({ ...f, periodicidades: e.target.checked ? [...f.periodicidades, k] : f.periodicidades.filter((x: string) => x !== k) })} />{t}</label>)}</div></fieldset>
          </div></section>
        <section className="tarjeta p-5"><h2 className="font-semibold text-marino">Condiciones y textos</h2>
          <div className="mt-3 grid gap-3">
            {txt("condiciones", "Condiciones comerciales generales", { area: 3 })}{txt("instrucciones_contratar", "Cómo contratar o pedir ajustes", { area: 2 })}
            {txt("notas_pie", "Nota al pie del PDF (máx. 150)", { max: 150 })}
          </div></section>
        <section className="tarjeta p-5"><h2 className="font-semibold text-marino">Correo de la cotización</h2>
          <p className={`mt-1 text-sm ${integ?.correo.configurado ? "text-emerald-700" : "text-amber-800"}`}>{integ?.correo.configurado ? `Correo configurado (${integ.correo.proveedor || "prueba"}${integ.correo.prueba ? ", modo de prueba: no sale" : ""}).` : "El correo NO está configurado: las cotizaciones no se envían desde Nomira (se puede descargar el PDF y copiar el texto)."}</p>
          <div className="mt-3 grid gap-3">
            {txt("asunto_correo", "Asunto (use {folio}, {nombre_comercial}, {despacho})", { max: 200 })}{txt("mensaje_presentacion", "Mensaje de presentación por defecto", { area: 3 })}
          </div></section>
        <section className="tarjeta p-5 xl:col-span-2"><h2 className="font-semibold text-marino">Formas de pago</h2>
          <p className="text-sm text-slate-500">Una forma de pago solo aparece en la cotización si está habilitada y completa. No capture datos bancarios de ejemplo.</p>
          {integ?.faltantes_pago.length > 0 && <div className="mt-2"><Aviso tipo="alerta">{integ.faltantes_pago.join(" ")}</Aviso></div>}
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            <div className="rounded-xl border border-crema-300 p-3">
              <label className="flex items-center gap-2 font-semibold text-marino"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={f.pago_tarjeta} onChange={set("pago_tarjeta")} />Tarjeta (Stripe Checkout)</label>
              <p className="mt-1 text-xs text-slate-600">{integ?.stripe.conectado ? (integ.stripe.modo === "real" ? <b className="text-red-700">Stripe conectado en MODO REAL: los pagos con tarjeta son cobros reales.</b> : "Stripe conectado en MODO DE PRUEBA (sin dinero real).") : integ?.stripe.motivo}</p>
              <p className="mt-1 text-xs text-slate-500">Se configura en el servidor: STRIPE_MODO (prueba o real), STRIPE_SECRET_KEY y STRIPE_WEBHOOK_SECRET. Nomira no guarda datos de tarjeta.</p>
            </div>
            <div className="rounded-xl border border-crema-300 p-3">
              <label className="flex items-center gap-2 font-semibold text-marino"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={f.spei_habilitado} onChange={set("spei_habilitado")} />Transferencia SPEI</label>
              <div className="mt-2 grid gap-2">{txt("spei_banco", "Banco")}{txt("spei_titular", "Titular")}{txt("spei_clabe", "CLABE (18 dígitos)", { max: 18, modo: "numeric" })}{txt("spei_instrucciones", "Instrucciones", { area: 2 })}</div>
            </div>
            <div className="rounded-xl border border-crema-300 p-3">
              <label className="flex items-center gap-2 font-semibold text-marino"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={f.otro_habilitado} onChange={set("otro_habilitado")} />Otra forma de pago</label>
              <div className="mt-2 grid gap-2">{txt("otro_nombre", "Nombre (p. ej. depósito en ventanilla)")}{txt("otro_instrucciones", "Instrucciones", { area: 3 })}</div>
            </div>
          </div></section>
        <section className="tarjeta p-5"><h2 className="font-semibold text-marino">Propuesta del cliente</h2>
          <label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={f.aceptacion_en_linea} onChange={set("aceptacion_en_linea")} />
            <span>Permitir que el cliente registre su aceptación en línea. <span className="block text-xs text-slate-500">Se guarda la versión aceptada, fecha, hora y nombre. Su validez como aceptación electrónica debe revisarla su abogado.</span></span></label>
        </section>
        <section className="tarjeta p-5"><h2 className="font-semibold text-marino">Registro en línea</h2>
          <label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={!!f.registro_prueba} onChange={set("registro_prueba")} />
            <span>Permitir que los despachos se registren solos con prueba gratuita de 2 días. <span className="block text-xs text-slate-500">Eligen hasta 3 módulos, confirman su correo (o entran con Google) y llegan a Ventas como lead. Al terminar la prueba se bloquea el uso hasta contratar; sus datos se conservan.</span></span></label>
        </section>
        <section className="tarjeta p-5"><h2 className="font-semibold text-marino">Precios en el sitio web</h2>
          <div className="mt-3 space-y-2 text-sm">
            <label className="flex items-center gap-2"><input type="radio" name="pp" className="accent-turquesa" checked={f.precios_publicos === "ocultos"} onChange={() => setF({ ...f, precios_publicos: "ocultos" })} />No mostrar precios</label>
            <label className="flex items-center gap-2"><input type="radio" name="pp" className="accent-turquesa" checked={f.precios_publicos === "desde"} onChange={() => setF({ ...f, precios_publicos: "desde" })} />Mostrar solo «Paquetes desde $X MXN + IVA» (precio del paquete activo más bajo)</label>
            <p className="text-xs text-slate-500">Nunca se publica el desglose de paquetes ni de adicionales.</p>
          </div></section>
      </div>
      <div className="sticky bottom-0 mt-5 flex items-center justify-end gap-3 border-t border-crema-300 bg-crema/90 py-3 backdrop-blur">
        <div className="flex-1"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
        <button className="btn-turquesa" onClick={guardar}>Guardar configuración</button>
      </div>
    </ComercialShell>
  );
}
