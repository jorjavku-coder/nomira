"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

function Estado({ x }: { x: any }) {
  return x.conectado
    ? <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Conectado{x.prueba ? " · modo de prueba" : ""} ({x.pista})</span>
    : <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">Sin conectar</span>;
}

export default function CobroFacturacion() {
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [stripe, setStripe] = useState("");
  const [facturapi, setFacturapi] = useState("");
  const [fiscal, setFiscal] = useState<any>({});
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    api.get("/cobro/config").then((r) => { setC(r); setFiscal({ clave_producto: r.clave_producto || "", clave_unidad: r.clave_unidad, uso_cfdi: r.uso_cfdi, retenciones: r.retenciones }); })
      .catch((e) => setError(e.message));
  }, []);
  async function guardar(cuerpo: any, msg: string) {
    setError(""); setOk(""); setGuardando(true);
    try { const r = await api.put("/cobro/config", cuerpo); setC(r); setOk(msg); setStripe(""); setFacturapi(""); }
    catch (e: any) { setError(e.message); } finally { setGuardando(false); }
  }
  if (!c) return <Shell><Aviso>{error}</Aviso></Shell>;
  const admin = c.es_admin;
  return (
    <Shell>
      <Link href="/clientes" className="text-sm font-semibold text-turquesa-700">← Clientes</Link>
      <h1 className="mt-2 text-3xl font-extrabold text-marino">Cobro en línea y facturación</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">Conecta <b>tus propias cuentas</b>: el dinero llega directo a tu Stripe y las facturas salen con tus sellos desde tu Facturapi. Nomira guarda las llaves cifradas, nunca las vuelve a mostrar y no ve datos de tarjeta.</p>
      <div className="my-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
        {!admin && <Aviso tipo="info">Solo un administrador del despacho puede cambiar esta configuración.</Aviso>}</div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="tarjeta p-5" aria-label="Stripe">
          <div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-marino">1. Ligas de pago con Stripe</h2><Estado x={c.stripe} /></div>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-slate-700">
            <li>Entra a tu cuenta de Stripe (o créala en stripe.com y verifica tu negocio).</li>
            <li>En <b>Configuración → Métodos de pago</b> activa los que quieras: tarjeta, OXXO, transferencia.</li>
            <li>Ve a <b>Desarrolladores → Claves de API → Crear clave restringida</b>. Dale permiso de <b>escritura en «Checkout Sessions»</b> y nada más.</li>
            <li>Copia la clave (empieza con <code>rk_live_</code>) y pégala aquí. Para probar sin dinero real usa una de prueba (<code>rk_test_</code>).</li>
          </ol>
          {admin && <form className="mt-4 space-y-2" onSubmit={(e) => { e.preventDefault(); guardar({ stripe_llave: stripe }, "Stripe conectado."); }}>
            <label className="block"><span className="etiqueta">Clave de Stripe</span>
              <input className="campo font-mono" type="password" autoComplete="off" value={stripe} onChange={(e) => setStripe(e.target.value)} placeholder="rk_live_…" required /></label>
            <div className="flex flex-wrap gap-2"><button className="btn-turquesa" disabled={guardando}>{guardando ? "Revisando…" : c.stripe.conectado ? "Cambiar clave" : "Conectar Stripe"}</button>
              {c.stripe.conectado && <button type="button" className="btn-sec" onClick={() => guardar({ stripe_llave: "" }, "Stripe desconectado.")}>Desconectar</button>}</div>
          </form>}
          <p className="mt-3 text-xs text-slate-500">Cuando tu cliente paga, Nomira lo confirma con Stripe y registra el pago en su cuenta (al abrir la ficha y cada 15 minutos).</p>
        </section>

        <section className="tarjeta p-5" aria-label="Facturapi">
          <div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-marino">2. Facturas CFDI 4.0 con Facturapi</h2><Estado x={c.facturapi} /></div>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-slate-700">
            <li>Crea tu cuenta en facturapi.io y captura los datos fiscales del despacho.</li>
            <li>Sube tu <b>CSD</b> (certificado de sello digital: archivos .cer y .key con su contraseña) en Facturapi. Nomira no los pide ni los guarda.</li>
            <li>En <b>Desarrolladores → Claves de API</b> copia la clave secreta «Live» (<code>sk_live_</code>) o la de pruebas (<code>sk_test_</code>).</li>
          </ol>
          {admin && <form className="mt-4 space-y-2" onSubmit={(e) => { e.preventDefault(); guardar({ facturapi_llave: facturapi }, "Facturapi conectado."); }}>
            <label className="block"><span className="etiqueta">Clave secreta de Facturapi</span>
              <input className="campo font-mono" type="password" autoComplete="off" value={facturapi} onChange={(e) => setFacturapi(e.target.value)} placeholder="sk_live_…" required /></label>
            <div className="flex flex-wrap gap-2"><button className="btn-turquesa" disabled={guardando}>{guardando ? "Revisando…" : c.facturapi.conectado ? "Cambiar clave" : "Conectar Facturapi"}</button>
              {c.facturapi.conectado && <button type="button" className="btn-sec" onClick={() => guardar({ facturapi_llave: "" }, "Facturapi desconectado.")}>Desconectar</button>}</div>
          </form>}
        </section>
      </div>

      <section className="tarjeta mt-5 p-5" aria-label="Datos fiscales de las facturas">
        <h2 className="font-semibold text-marino">3. Datos de tus facturas</h2>
        <p className="mt-1 text-sm text-slate-600">Confírmalos con tu contador. Las claves del SAT que empiezan con 8012 corresponden a servicios legales.</p>
        <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); guardar(fiscal, "Datos de facturación guardados."); }}>
          <label className="block"><span className="etiqueta">Clave de producto o servicio (8 dígitos)</span>
            <input className="campo" inputMode="numeric" pattern="\d{8}" value={fiscal.clave_producto} disabled={!admin} onChange={(e) => setFiscal({ ...fiscal, clave_producto: e.target.value })} placeholder="8012…" /></label>
          <label className="block"><span className="etiqueta">Clave de unidad</span>
            <input className="campo" value={fiscal.clave_unidad} disabled={!admin} onChange={(e) => setFiscal({ ...fiscal, clave_unidad: e.target.value.toUpperCase() })} placeholder="E48" /></label>
          <label className="block"><span className="etiqueta">Uso de CFDI más común</span>
            <select className="campo" value={fiscal.uso_cfdi} disabled={!admin} onChange={(e) => setFiscal({ ...fiscal, uso_cfdi: e.target.value })}>
              {Object.entries(c.usos).map(([k, v]) => <option key={k} value={k}>{k} · {v as string}</option>)}</select></label>
          <label className="block"><span className="etiqueta">Retenciones (solo a clientes persona moral)</span>
            <select className="campo" value={fiscal.retenciones} disabled={!admin} onChange={(e) => setFiscal({ ...fiscal, retenciones: e.target.value })}>
              {Object.entries(c.opciones_retenciones).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
          {admin && <div className="sm:col-span-2"><button className="btn-turquesa" disabled={guardando}>Guardar datos</button></div>}
        </form>
        <p className="mt-3 text-xs text-slate-500">Para facturar, cada cliente necesita RFC, régimen fiscal (por ejemplo 601 o 612) y código postal fiscal. Puedes leerlos de su constancia de situación fiscal en su ficha.</p>
      </section>
    </Shell>
  );
}
