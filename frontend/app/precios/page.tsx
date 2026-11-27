"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import Logo from "@/components/Logo";
import { mxn } from "@/lib/api";

const entero = (v: string) => mxn(v).replace(/\.00$/, "");
async function pedir(ruta: string, cuerpo?: unknown) {
  const r = await fetch(`/api/precios${ruta}`, cuerpo === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(typeof j.detail === "string" ? j.detail : "No se pudo calcular. Revise su selección."), { status: r.status });
  return j;
}

/** Precios públicos con carrito: la persona arma su plan, ve el total (lo calcula el servidor) y recibe su cotización formal. */
export default function Precios() {
  const [cat, setCat] = useState<any>(null);
  const [oculto, setOculto] = useState(false);
  const [paq, setPaq] = useState<number | null>(null);
  const [mods, setMods] = useState<string[]>([]);
  const [per, setPer] = useState("mensual");
  const [usuarios, setUsuarios] = useState(0);
  const [cupon, setCupon] = useState("");
  const [cuponAplicado, setCuponAplicado] = useState("");
  const [calc, setCalc] = useState<any>(null);
  const [error, setError] = useState("");
  const [errorCupon, setErrorCupon] = useState("");
  const [pagar, setPagar] = useState<string | null>(null);
  useEffect(() => {
    pedir("").then((c) => { setCat(c); const medio = c.paquetes[Math.min(1, c.paquetes.length - 1)]; setPaq(medio?.id ?? null); setPer(c.periodicidades[0]?.clave || "mensual"); })
      .catch((e) => { if (e.status === 404) setOculto(true); else setError(e.message); });
  }, []);
  const paquete = cat?.paquetes.find((p: any) => p.id === paq);
  const entrada = useMemo(() => ({ paquete_id: paq, modulos: mods, periodicidad: per, usuarios_extra: usuarios, cupon: cuponAplicado || null }), [paq, mods, per, usuarios, cuponAplicado]);
  useEffect(() => {
    if (!paq || !mods.length) { setCalc(null); return; }
    const t = setTimeout(() => pedir("/calcular", entrada).then((r) => { setCalc(r); setError(""); }).catch((e) => {
      if (cuponAplicado) { setErrorCupon(e.message); setCuponAplicado(""); } else { setCalc(null); setError(e.message); }
    }), 250);
    return () => clearTimeout(t);
  }, [entrada, paq, mods.length, cuponAplicado]);
  const alternar = (k: string) => setMods(mods.includes(k) ? mods.filter((x) => x !== k) : [...mods, k]);
  const incluidos = paquete ? mods.slice(0, paquete.modulos_incluidos) : [];

  if (oculto) return <Marco><div className="tarjeta mx-auto max-w-xl p-10 text-center"><h1 className="font-marca text-3xl font-extrabold text-marino">Cotice su plan</h1>
    <p className="mt-2 text-slate-600">Por ahora preparamos cada cotización a la medida.</p><Link href="/#informes" className="btn-turquesa mt-5 inline-block">Solicitar cotización</Link></div></Marco>;
  return (
    <Marco>
      <p className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Precios en pesos mexicanos</p>
      <h1 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Arme su plan y reciba su cotización al instante</h1>
      <p className="mt-2 max-w-3xl text-slate-600">Elija un paquete y los módulos que usará. Verá el total con IVA y, al terminar, le llega su cotización formal para aceptarla y pagarla en línea.</p>
      {!cat && !error && <p className="mt-8 text-sm text-slate-500">Cargando precios…</p>}
      {cat && <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          {cat.periodicidades.length > 1 && <div className="flex w-fit rounded-xl bg-white p-1 ring-1 ring-crema-300" role="radiogroup" aria-label="Forma de pago">
            {cat.periodicidades.map((p: any) => <button key={p.clave} role="radio" aria-checked={per === p.clave} onClick={() => setPer(p.clave)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${per === p.clave ? "bg-marino text-white" : "text-slate-600"}`}>Pago {p.nombre.toLowerCase()}</button>)}</div>}

          <section aria-labelledby="t-paq"><h2 id="t-paq" className="text-lg font-bold text-marino">1. Elija su paquete</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">{cat.paquetes.map((p: any, i: number) => (
              <button key={p.id} onClick={() => setPaq(p.id)} aria-pressed={paq === p.id}
                className={`tarjeta relative p-5 text-left transition ${paq === p.id ? "ring-2 ring-turquesa" : "hover:-translate-y-0.5"}`}>
                {i === 1 && <span className="absolute -top-2.5 left-4 rounded-full bg-turquesa px-2 py-0.5 text-[11px] font-bold text-white">Recomendado</span>}
                <p className="font-bold text-marino">{p.nombre}</p>
                <p className="mt-1"><span className="font-marca text-3xl font-extrabold text-marino">{entero(p.precio_mensual)}</span><span className="text-sm text-slate-500"> /mes + IVA</span></p>
                <ul className="mt-3 space-y-1 text-sm text-slate-600">
                  <li>✓ {p.modulos_incluidos} {p.modulos_incluidos === 1 ? "módulo incluido" : "módulos incluidos"}</li>
                  <li>✓ {p.usuarios} usuarios</li><li>✓ {p.almacenamiento_gb} GB de almacenamiento</li>
                  <li>✓ Clientes y cobranza, tesis, asistente IA y Club Nomira</li></ul>
                {p.descripcion && <p className="mt-2 text-xs text-slate-500">{p.descripcion}</p>}
              </button>))}</div></section>

          <section aria-labelledby="t-mods"><h2 id="t-mods" className="text-lg font-bold text-marino">2. Elija sus módulos</h2>
            {paquete && <p className="text-sm text-slate-500">Los primeros {paquete.modulos_incluidos} que marque van incluidos; los demás se suman a su mensualidad.</p>}
            <div className="mt-3 grid gap-2 sm:grid-cols-2">{cat.modulos.filter((x: any) => x.precio_adicional).map((x: any) => {
              const sel = mods.includes(x.clave), inc = incluidos.includes(x.clave);
              return <label key={x.clave} className={`tarjeta flex cursor-pointer items-start gap-3 p-4 transition ${sel ? "ring-2 ring-turquesa" : ""}`}>
                <input type="checkbox" className="mt-1 h-4 w-4 accent-turquesa" checked={sel} onChange={() => alternar(x.clave)} />
                <span className="min-w-0 flex-1"><span className="flex items-center justify-between gap-2"><b className="text-marino">{x.nombre}</b>
                  <span className={`shrink-0 text-xs font-bold ${inc ? "text-emerald-700" : "text-slate-500"}`}>{inc ? "Incluido" : `+${entero(x.precio_adicional)}/mes`}</span></span>
                  {x.descripcion && <span className="mt-0.5 block text-xs text-slate-500">{x.descripcion}</span>}</span></label>;
            })}</div></section>

          {cat.usuario_extra && <section aria-labelledby="t-us" className="tarjeta flex flex-wrap items-center justify-between gap-3 p-5">
            <div><h2 id="t-us" className="font-bold text-marino">3. ¿Necesita más usuarios?</h2>
              <p className="text-sm text-slate-500">{paquete ? `Su paquete incluye ${paquete.usuarios}. ` : ""}Cada usuario adicional: {entero(cat.usuario_extra)}/mes.</p></div>
            <div className="flex items-center gap-2"><button className="btn-sec h-10 w-10 p-0" aria-label="Quitar un usuario" onClick={() => setUsuarios(Math.max(0, usuarios - 1))}>−</button>
              <span className="w-10 text-center text-lg font-bold tabular-nums" aria-live="polite">{usuarios}</span>
              <button className="btn-sec h-10 w-10 p-0" aria-label="Agregar un usuario" onClick={() => setUsuarios(Math.min(200, usuarios + 1))}>+</button></div>
          </section>}
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <div className="tarjeta space-y-4 p-6" aria-live="polite">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500">🛒 Su plan</p>
            {!mods.length ? <p className="text-sm text-slate-500">Marque al menos un módulo para ver el total.</p> : calc ? <>
              <ul className="space-y-1.5 text-sm">{calc.lineas.map((l: any, k: number) => (
                <li key={k} className="flex justify-between gap-3"><span className="text-slate-700">{l.concepto}{l.cantidad > 1 ? ` × ${l.cantidad}` : ""}</span><span className="tabular-nums text-slate-700">{mxn(l.importe)}</span></li>))}</ul>
              <dl className="space-y-1 border-t border-crema-300 pt-3 text-sm">
                {calc.cupon && <div className="flex justify-between text-emerald-700"><dt>Cupón {calc.cupon.codigo}</dt><dd className="tabular-nums">−{mxn(calc.cupon.importe)}</dd></div>}
                <div className="flex justify-between"><dt className="text-slate-500">Subtotal</dt><dd className="tabular-nums">{mxn(calc.base_iva)}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">IVA {Number(calc.iva_pct)}%</dt><dd className="tabular-nums">{mxn(calc.iva)}</dd></div></dl>
              <div><p className="text-xs text-slate-500">Total {calc.periodicidad.meses === 1 ? "al mes" : `por ${calc.periodicidad.meses} meses`}</p>
                <p className="font-marca text-4xl font-extrabold text-marino" data-prueba="total">{mxn(calc.total)}</p></div>
            </> : <p className="text-sm text-slate-500">Calculando…</p>}
            {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
            <div className="flex gap-2"><input className="campo" placeholder="Cupón (opcional)" aria-label="Cupón" value={cupon} onChange={(e) => setCupon(e.target.value.toUpperCase())} />
              <button className="btn-sec" disabled={!cupon.trim() || !mods.length} onClick={() => { setErrorCupon(""); setCuponAplicado(cupon.trim()); }}>Aplicar</button></div>
            {errorCupon && <p role="alert" className="text-sm text-red-700">{errorCupon}</p>}
            <button className="btn-turquesa w-full py-3 text-base" disabled={!calc} onClick={() => setPagar(calc.total)}>Comprar este plan</button>
            <p className="text-xs text-slate-500">Recibirá una cotización formal con folio, válida {cat.vigencia_dias} días.{cat.formas_pago.length ? ` Formas de pago: ${cat.formas_pago.join(", ")}.` : ""}</p>
          </div>
        </aside>
      </div>}
      {!cat && error && <p role="alert" className="mt-6 text-sm text-red-700">{error}</p>}
      {pagar && <Datos entrada={entrada} total={pagar} onCerrar={() => setPagar(null)} />}
    </Marco>
  );
}

function Marco({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-crema">
      <header className="border-b border-crema-300 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-5 py-3">
          <Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
          <div className="flex items-center gap-4 text-sm"><Link href="/login?registro=1" className="font-semibold text-marino hover:underline">Probar 2 días gratis</Link>
            <Link href="/login" className="btn-sec">Iniciar sesión</Link></div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-10">{children}</main>
    </div>
  );
}

function Datos({ entrada, total, onCerrar }: { entrada: any; total: string; onCerrar: () => void }) {
  const [f, setF] = useState({ contacto: "", despacho: "", email: "", telefono: "", sitio_web: "" });
  const [acepto, setAcepto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [listo, setListo] = useState<any>(null);
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const enviar = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setEnviando(true);
    try { setListo(await pedir("/cotizar", { ...entrada, ...f, telefono: f.telefono || null, acepto })); } catch (err: any) { setError(err.message); } finally { setEnviando(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-marino-900/55 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Datos para su cotización">
      <div className="tarjeta mt-8 w-full max-w-lg p-6 shadow-flotante">
        {listo ? <div className="text-center">
          <p className="text-4xl" aria-hidden>🎉</p>
          <h2 className="mt-2 text-2xl font-bold text-marino">Su cotización {listo.folio} está lista</h2>
          <p className="mt-1 text-slate-600">Total: <b className="text-marino">{mxn(listo.total)}</b> con IVA.</p>
          <p className="mt-2 text-sm text-slate-600">{listo.correo_enviado ? "También se la enviamos a su correo con el PDF." : "Guarde este enlace: ahí puede verla, descargarla en PDF y pagarla."}</p>
          <a href={listo.url} className="btn-turquesa mt-5 inline-block w-full py-3 text-base">Ver, aceptar y pagar mi cotización</a>
          <button className="mt-3 text-sm text-slate-500 hover:underline" onClick={onCerrar}>Cerrar</button>
        </div> : <form onSubmit={enviar} className="space-y-3">
          <div className="flex items-start justify-between gap-3"><div><h2 className="text-xl font-bold text-marino">¿A nombre de quién?</h2>
            <p className="text-sm text-slate-500">Total de su plan: <b className="text-marino">{mxn(total)}</b> con IVA.</p></div>
            <button type="button" className="btn-sec" onClick={onCerrar}>Cerrar</button></div>
          <label className="block"><span className="etiqueta">Su nombre</span><input className="campo" required minLength={2} autoComplete="name" value={f.contacto} onChange={pon("contacto")} /></label>
          <label className="block"><span className="etiqueta">Despacho o notaría</span><input className="campo" required minLength={2} autoComplete="organization" value={f.despacho} onChange={pon("despacho")} /></label>
          <label className="block"><span className="etiqueta">Correo electrónico</span><input className="campo" type="email" required autoComplete="email" value={f.email} onChange={pon("email")} /></label>
          <label className="block"><span className="etiqueta">Teléfono (opcional)</span><input className="campo" type="tel" autoComplete="tel" value={f.telefono} onChange={pon("telefono")} /></label>
          <input className="hidden" tabIndex={-1} autoComplete="off" aria-hidden value={f.sitio_web} onChange={pon("sitio_web")} name="sitio_web" />
          <label className="flex items-start gap-2 text-sm text-slate-600"><input type="checkbox" className="mt-1" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} required />
            <span>Leí el <Link href="/legal/privacidad" target="_blank" className="font-semibold text-turquesa-700 underline">aviso de privacidad</Link> y acepto que Nomira me envíe esta cotización.</span></label>
          {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
          <button className="btn-turquesa w-full py-3 text-base" disabled={enviando || !acepto}>{enviando ? "Preparando su cotización…" : "Recibir mi cotización"}</button>
        </form>}
      </div>
    </div>
  );
}
