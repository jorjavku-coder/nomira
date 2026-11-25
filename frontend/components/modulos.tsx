"use client";
import { useCallback, useEffect, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api, mxn } from "@/lib/api";

type Mod = {
  clave: string; nombre: string; descripcion: string; contratado: boolean; activo: boolean;
  precio: string | null; iva: string | null; total: string | null; de_prueba: boolean;
  suscripcion: { estado: string; desde: string | null } | null;
};
type Tienda = { modulos: Mod[]; en_prueba: boolean; pago_en_linea: boolean; es_admin: boolean };

/** Todos los módulos con su interruptor: encendidos los activos, apagados los demás. Encender uno que no tienen
 *  abre su precio y la compra directa (o lo enciende gratis durante la prueba). Solo el administrador decide. */
export function TiendaModulos() {
  const [t, setT] = useState<Tienda | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [elegido, setElegido] = useState<Mod | null>(null);
  const [cancelar, setCancelar] = useState<Mod | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const cargar = useCallback(() => api.get("/organizacion/modulos/tienda").then((x: Tienda) => { setT(x); return x; }).catch((e) => { setError(e.message); return null; }), []);
  useEffect(() => {
    cargar();
    const q = new URLSearchParams(window.location.search);
    if (q.get("compra") === "cancelada") setError("No se completó el pago. Puede intentarlo de nuevo cuando quiera.");
    if (q.get("compra") === "procesando") {
      const clave = q.get("modulo");
      setOk("Recibimos su pago. Estamos encendiendo el módulo; tarda unos segundos…");
      let n = 0;
      const timer = setInterval(async () => {
        n++;
        const x = await cargar();
        if (x?.modulos.find((md) => md.clave === clave)?.activo) {
          clearInterval(timer); setOk("¡Listo! El módulo ya está encendido y aparece en su menú.");
          window.dispatchEvent(new Event("nomira:modulos"));
        } else if (n >= 15) { clearInterval(timer); setOk("Su pago está en proceso. En cuanto Stripe lo confirme, el módulo se encenderá solo."); }
      }, 3000);
      return () => clearInterval(timer);
    }
  }, [cargar]);

  async function hacer(fn: () => Promise<any>) {
    setError(""); setOk(""); setOcupado(true);
    try { return await fn(); } catch (e: any) { setError(e.message); } finally { setOcupado(false); }
  }
  async function cambiar(md: Mod, encender: boolean) {
    if (!t?.es_admin) { setError("Solo el administrador del despacho puede encender o apagar módulos."); return; }
    if (md.contratado) {
      if (!encender && !confirm(`¿Apagar «${md.nombre}»? Su equipo dejará de verlo; los datos se conservan.`)) return;
      if (await hacer(() => api.patch(`/organizacion/modulos/${md.clave}`, { activo: encender }))) setOk(encender ? "Módulo activado." : "Módulo desactivado. Sus datos se conservan.");
      await cargar(); window.dispatchEvent(new Event("nomira:modulos"));
      return;
    }
    if (encender) setElegido(md);
  }
  async function contratar(md: Mod) {
    const r = await hacer(() => api.post(`/organizacion/modulos/${md.clave}/contratar`, {}));
    if (!r) return;
    if (r.url) { window.location.href = r.url; return; }
    setElegido(null);
    setOk(r.en_prueba ? `«${md.nombre}» encendido. Úselo gratis durante su prueba.` : `«${md.nombre}» encendido.`);
    await cargar(); window.dispatchEvent(new Event("nomira:modulos"));
  }

  if (!t) return <section className="tarjeta mt-5 p-6"><Aviso>{error}</Aviso><p className="text-sm text-slate-500">{error ? "" : "Cargando módulos…"}</p></section>;
  return (
    <section id="modulos" className="tarjeta mt-5 scroll-mt-4 p-6">
      <h2 className="text-lg font-bold text-marino">Módulos de su despacho</h2>
      <p className="mt-1 text-sm text-slate-500">{t.en_prueba
        ? "Está en su prueba gratis: encienda los módulos que quiera probar, sin costo, hasta que termine la prueba."
        : "Encienda el módulo que necesite: verá su precio y lo contrata en línea, con cargo mensual a su tarjeta. Apagar un módulo solo oculta su sección: los datos se conservan."}</p>
      <div className="mt-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">{t.modulos.map((md) => (
        <div key={md.clave} className={`rounded-xl border p-4 ${md.activo ? "border-turquesa bg-turquesa-50/60" : "border-crema-300 bg-white"}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="font-marca font-bold text-marino">{md.nombre}</div>
              <p className="mt-0.5 text-xs text-slate-600">{md.descripcion}</p>
            </div>
            <label className="flex shrink-0 cursor-pointer items-center gap-2 text-sm font-semibold text-marino">
              <input type="checkbox" role="switch" className="h-5 w-5 accent-turquesa" checked={md.activo} disabled={ocupado || !t.es_admin}
                aria-label={`${md.activo ? "Apagar" : "Encender"} ${md.nombre}`} onChange={(e) => cambiar(md, e.target.checked)} />
              {md.activo ? "Encendido" : "Apagado"}
            </label>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            {md.de_prueba && <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">Gratis durante la prueba</span>}
            {md.suscripcion?.estado === "activa" && <span className="text-emerald-700">Contratado en línea · cargo mensual {md.total && `de ${mxn(md.total)}`}</span>}
            {md.suscripcion?.estado === "pago_fallido" && <span className="font-semibold text-red-700">No se pudo cobrar este mes. Revise su tarjeta: Stripe volverá a intentarlo.</span>}
            {md.suscripcion?.estado === "cancelando" && <span className="text-amber-800">Cancelado: se apagará al terminar el mes pagado.</span>}
            {md.suscripcion && md.suscripcion.estado !== "cancelando" && t.es_admin &&
              <button className="font-semibold text-slate-500 underline" onClick={() => setCancelar(md)}>Cancelar suscripción</button>}
            {!md.contratado && md.precio && <span className="text-slate-600">{mxn(md.precio)} al mes + IVA</span>}
            {!md.contratado && !md.precio && <span className="text-slate-500">Para contratarlo, escriba a <a href="/soporte" className="font-semibold text-turquesa-700 underline">Soporte</a>.</span>}
          </div>
          {!t.es_admin && !md.contratado && <p className="mt-1 text-xs text-slate-500">Pida a su administrador que lo encienda.</p>}
        </div>))}</div>

      {elegido && <Modal titulo={`Encender ${elegido.nombre}`} onCerrar={() => setElegido(null)}>
        <p className="text-sm text-slate-700">{elegido.descripcion}</p>
        {t.en_prueba ? <>
          <p className="mt-4 rounded-xl bg-turquesa-50 p-3 text-sm text-marino">Está en su prueba gratis: puede usarlo <b>sin costo</b> hasta que termine.
            {elegido.precio && <> Después cuesta {mxn(elegido.precio)} al mes + IVA si decide contratarlo.</>}</p>
          <button className="btn-turquesa mt-4 w-full py-2.5" disabled={ocupado} onClick={() => contratar(elegido)}>{ocupado ? "Encendiendo…" : "Encenderlo gratis"}</button>
        </> : elegido.precio ? <>
          <dl className="mt-4 space-y-1 rounded-xl border border-crema-300 p-4 text-sm">
            <div className="flex justify-between"><dt>Precio mensual</dt><dd>{mxn(elegido.precio)}</dd></div>
            <div className="flex justify-between text-slate-600"><dt>IVA</dt><dd>{mxn(elegido.iva)}</dd></div>
            <div className="flex justify-between border-t border-crema-300 pt-1 font-bold text-marino"><dt>Total al mes</dt><dd>{mxn(elegido.total)}</dd></div>
          </dl>
          <p className="mt-3 text-xs text-slate-500">Se cobra cada mes a su tarjeta hasta que lo cancele desde aquí. Paga en la página segura de Stripe: Nomira no ve ni guarda los datos de su tarjeta. El módulo se enciende en cuanto se confirma el pago.</p>
          {t.pago_en_linea
            ? <button className="btn-turquesa mt-4 w-full py-2.5" disabled={ocupado} onClick={() => contratar(elegido)}>{ocupado ? "Abriendo el pago…" : `Contratar por ${mxn(elegido.total)} al mes`}</button>
            : <p className="mt-4 text-sm text-amber-800">El pago en línea no está disponible por ahora. <a href={`/soporte?tema=${encodeURIComponent("Quiero contratar " + elegido.nombre)}`} className="font-semibold underline">Escríbanos</a> y lo activamos.</p>}
        </> : <p className="mt-4 text-sm">Este módulo aún no tiene precio en línea. <a href={`/soporte?tema=${encodeURIComponent("Quiero contratar " + elegido.nombre)}`} className="font-semibold text-turquesa-700 underline">Escríbanos</a> y lo activamos.</p>}
      </Modal>}

      {cancelar && <Modal titulo={`Cancelar ${cancelar.nombre}`} onCerrar={() => setCancelar(null)}>
        <p className="text-sm text-slate-700">Ya no se cobrará el siguiente mes. Podrá usarlo hasta que termine el mes que ya pagó; después se apaga solo y <b>sus datos se conservan</b>.</p>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setCancelar(null)}>Mantenerlo</button>
          <button className="btn-primario" disabled={ocupado} onClick={async () => {
            if (await hacer(() => api.post(`/organizacion/modulos/${cancelar.clave}/cancelar`, {}))) { setCancelar(null); setOk("Suscripción cancelada. Se apagará al terminar el mes pagado."); cargar(); }
          }}>Cancelar suscripción</button></div>
      </Modal>}
    </section>
  );
}
