"use client";
/** Módulo Comercial del panel (solo superadministrador): navegación, estados y constructor de
 *  cotizaciones. Todo importe lo calcula el servidor; aquí solo se muestra. */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ShellPlataforma, { useSesionP } from "@/components/plataforma";
import { Aviso } from "@/components/ui";
import { mxn } from "@/lib/api";
import { apiP, esSuperadmin } from "@/lib/plataforma";

export const COLOR_ESTADO: Record<string, string> = {
  borrador: "bg-amber-100 text-amber-800", revision: "bg-orange-100 text-orange-800", enviada: "bg-blue-100 text-blue-800",
  vista: "bg-indigo-100 text-indigo-800", aceptada: "bg-emerald-100 text-emerald-800", pendiente_pago: "bg-violet-100 text-violet-800",
  pagada: "bg-emerald-600 text-white", vencida: "bg-slate-200 text-slate-600", cancelada: "bg-red-100 text-red-700",
};

export function EstadoCot({ estado, texto }: { estado: string; texto: string }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${COLOR_ESTADO[estado] || "bg-slate-100"}`}>{texto}</span>;
}

export function ComercialShell({ children }: { children: React.ReactNode }) {
  const ruta = usePathname();
  const sesion = useSesionP();
  const super_ = !sesion || esSuperadmin(sesion);
  const deCotizaciones = ruta.startsWith("/plataforma/comercial/cotizaciones");
  const tabs: [string, string, boolean][] = (super_ ? [
    ["/plataforma/comercial", "Resumen", ruta === "/plataforma/comercial"],
    ["/plataforma/comercial/cotizaciones", "Cotizaciones", ruta.startsWith("/plataforma/comercial/cotizaciones")],
    ["/plataforma/comercial/paquetes", "Paquetes y precios", ruta.startsWith("/plataforma/comercial/paquetes")],
    ["/plataforma/comercial/configuracion", "Configuración comercial", ruta.startsWith("/plataforma/comercial/configuracion")],
    ["/plataforma/comercial/cupones", "Cupones", ruta.startsWith("/plataforma/comercial/cupones")],
  ] : [["/plataforma/ventas", "← Ventas", false], ["/plataforma/comercial/cotizaciones", "Cotizaciones", deCotizaciones],
    ["/plataforma/comercial/cupones", "Cupones", ruta.startsWith("/plataforma/comercial/cupones")]]) as [string, string, boolean][];
  return (
    <ShellPlataforma>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-amber-700">{super_ ? "Comercial · solo superadministrador" : "Cotizaciones · equipo de ventas"}</p>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-crema-300" aria-label="Comercial">
        {tabs.map(([href, t, activo]) => (
          <Link key={href} href={href} aria-current={activo ? "page" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${activo ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>{t}</Link>))}
      </nav>
      {sesion && !esSuperadmin(sesion) && !deCotizaciones && !ruta.startsWith("/plataforma/comercial/cupones")
        ? <Aviso>Solo un superadministrador de Nomira puede usar el módulo Comercial. Si su rol cambió, cierre sesión y vuelva a entrar.</Aviso>
        : children}
    </ShellPlataforma>
  );
}

export function useCatalogoCM(): [any, string, () => void] {
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const cargar = () => apiP.get("/comercial/catalogo").then(setC).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  return [c, error, cargar];
}

/** Abre un PDF del panel en otra pestaña (lleva la sesión en el encabezado, no en la URL). */
export async function abrirPdf(ruta: string, nombre: string, descargar = false) {
  const b = await apiP.blob(ruta);
  const url = URL.createObjectURL(b);
  if (descargar) {
    const a = document.createElement("a");
    a.href = url; a.download = nombre; a.click();
  } else window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

const aLocal = (iso: string) => {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
const hoyISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

export function Desglose({ calc }: { calc: any }) {
  if (!calc) return null;
  return (
    <div className="text-sm">
      <ul className="divide-y divide-crema-300">
        {calc.lineas.map((l: any, i: number) => (
          <li key={i} className="flex justify-between gap-3 py-1.5">
            <span>{l.concepto}{l.cantidad > 1 ? ` × ${l.cantidad}` : ""}{l.tipo === "unico" ? <span className="text-slate-500"> (pago único)</span> : l.meses > 1 ? <span className="text-slate-500"> × {l.meses} meses</span> : null}
              {l.detalle && <span className="block text-xs text-slate-500">{l.detalle}</span>}</span>
            <span className="whitespace-nowrap font-medium">{mxn(l.importe)}</span>
          </li>))}
      </ul>
      <dl className="mt-2 space-y-1 border-t border-crema-300 pt-2">
        <div className="flex justify-between"><dt>Subtotal</dt><dd>{mxn(calc.subtotal)}</dd></div>
        {calc.descuento && <div className="flex justify-between text-emerald-700"><dt>Descuento</dt><dd>-{mxn(calc.descuento.importe)}</dd></div>}
        {calc.cupon && <div className="flex justify-between text-emerald-700"><dt>Cupón {calc.cupon.codigo} ({calc.cupon.texto})</dt><dd>-{mxn(calc.cupon.importe)}</dd></div>}
        <div className="flex justify-between"><dt>IVA ({Number(calc.iva_pct)}%)</dt><dd>{mxn(calc.iva)}</dd></div>
        <div className="flex justify-between rounded-xl bg-turquesa-700 px-3 py-2 text-base font-bold text-white"><dt>Total MXN</dt><dd>{mxn(calc.total)}</dd></div>
      </dl>
      <p className="mt-2 text-xs text-slate-500">{calc.usuarios.total} usuarios internos · {calc.almacenamiento.total_gb} GB · cobro {calc.periodicidad.nombre.toLowerCase()}
        {calc.asuntos_estimados ? ` · referencia aproximada: ~${calc.asuntos_estimados.toLocaleString("es-MX")} asuntos (no es un límite)` : ""}</p>
    </div>
  );
}

const PASOS = ["Cliente", "Paquete y módulos", "Condiciones", "Revisión"];

/** Constructor por pasos. Crea (sin `cot`) o edita (con `cot`) una cotización. */
export function Constructor({ cat, cot, onGuardado, onCancelar, inicial }: { cat: any; cot?: any; onGuardado: (d: any) => void; onCancelar?: () => void;
  inicial?: { contacto?: string; despacho?: string; email?: string; telefono?: string; necesidad?: string; oportunidad_id?: number } }) {
  const router = useRouter();
  const conf = cat.config;
  const activos = cat.paquetes.filter((p: any) => p.estado === "activo");
  const vInicial = (() => { const d = new Date(); d.setDate(d.getDate() + (conf.vigencia_dias || 15)); d.setHours(23, 59, 0, 0); return aLocal(d.toISOString()); })();
  const e0 = cot?.version?.entrada;
  const [paso, setPaso] = useState(0);
  const [f, setF] = useState<any>(() => ({
    contacto: cot?.contacto || inicial?.contacto || "", despacho: cot?.despacho || inicial?.despacho || "", email: cot?.email || inicial?.email || "",
    telefono: cot?.telefono || inicial?.telefono || "", necesidad: cot?.necesidad || inicial?.necesidad || "", notas_internas: cot?.notas_internas || "", preparada_por: cot?.version?.preparada_por || "",
    vence_en: cot ? aLocal(cot.vence_en) : vInicial,
    entrada: e0 ? { ...e0, descuento: e0.descuento || null, servicios: e0.servicios || [] } : {
      paquete_id: activos[0]?.id || null, modulos: [], incluidos: [], usuarios_extra: 0, bloques_extra: 0, periodicidad: cat.periodicidades[0]?.clave || "mensual",
      servicios: [], descuento: null, emision: hoyISO(), condiciones_pago: "", fecha_limite_pago: "", terminos: "", observaciones: "",
    },
  }));
  const [calc, setCalc] = useState<any>(null);
  const [errCalc, setErrCalc] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const t = useRef<any>(null);
  const e = f.entrada;
  const paq = cat.paquetes.find((p: any) => p.id === e.paquete_id);
  const setE = (cambios: any) => setF((x: any) => ({ ...x, entrada: { ...x.entrada, ...cambios } }));
  const set = (k: string) => (ev: any) => setF({ ...f, [k]: ev.target.value });

  useEffect(() => {
    clearTimeout(t.current);
    t.current = setTimeout(() => {
      if (!e.paquete_id || !e.modulos.length) { setCalc(null); setErrCalc(e.paquete_id ? "Elija al menos un módulo." : "Elija un paquete."); return; }
      apiP.post("/comercial/calcular", { entrada: e }).then((r) => { setCalc(r); setErrCalc(""); }).catch((x) => { setCalc(null); setErrCalc(x.message); });
    }, 300);
    return () => clearTimeout(t.current);
  }, [JSON.stringify(e)]); // eslint-disable-line react-hooks/exhaustive-deps

  function alternarModulo(clave: string) {
    const ya = e.modulos.includes(clave);
    const modulos = ya ? e.modulos.filter((x: string) => x !== clave) : [...e.modulos, clave];
    let incluidos = e.incluidos.filter((x: string) => modulos.includes(x));
    if (!ya && paq && incluidos.length < paq.modulos_incluidos) incluidos = [...incluidos, clave];
    setE({ modulos, incluidos });
  }
  function alternarIncluido(clave: string) {
    const inc = e.incluidos.includes(clave);
    if (!inc && paq && e.incluidos.length >= paq.modulos_incluidos) return setErrCalc(`El paquete ${paq.nombre} incluye ${paq.modulos_incluidos} módulo(s).`);
    setE({ incluidos: inc ? e.incluidos.filter((x: string) => x !== clave) : [...e.incluidos, clave] });
  }
  function servicio(clave: string) { return e.servicios.find((s: any) => s.clave === clave); }
  function setServicio(clave: string, cambios: any | null) {
    const resto = e.servicios.filter((s: any) => s.clave !== clave);
    setE({ servicios: cambios === null ? resto : [...resto, { clave, precio: "0", descripcion: "", ...servicio(clave), ...cambios }] });
  }
  const pasoValido = [
    f.contacto.trim().length >= 2 && f.despacho.trim().length >= 2 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim()),
    !!calc,
    !!calc && !!f.vence_en,
    !!calc,
  ];
  async function guardar() {
    setError(""); setGuardando(true);
    const cuerpo = { ...f, vence_en: new Date(f.vence_en).toISOString(), entrada: { ...e, fecha_limite_pago: e.fecha_limite_pago || null },
      ...(!cot && inicial?.oportunidad_id ? { oportunidad_id: inicial.oportunidad_id } : {}) };
    try {
      const r = cot ? await apiP.put(`/comercial/cotizaciones/${cot.id}`, cuerpo) : await apiP.post("/comercial/cotizaciones", cuerpo);
      onGuardado(r);
      if (!cot) router.push(`/plataforma/comercial/cotizaciones/${r.id}`);
    } catch (x: any) { setError(x.message); } finally { setGuardando(false); }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
      <section className="tarjeta p-5">
        <ol className="mb-5 flex flex-wrap gap-2 text-sm" aria-label="Pasos">
          {PASOS.map((p, i) => (
            <li key={p}><button type="button" onClick={() => i <= paso || pasoValido.slice(0, i).every(Boolean) ? setPaso(i) : null} aria-current={i === paso ? "step" : undefined}
              className={`rounded-full px-3 py-1.5 font-semibold ${i === paso ? "bg-marino text-white" : i < paso ? "bg-turquesa-50 text-turquesa-700" : "bg-crema-200 text-slate-500"}`}>{i + 1}. {p}</button></li>))}
        </ol>
        {cot?.acciones?.editar_crea_version && <div className="mb-4"><Aviso tipo="alerta">Esta cotización ya se envió. Al guardar se crea la <b>versión {cot.version_actual + 1}</b>; la versión enviada queda intacta.</Aviso></div>}

        {paso === 0 && <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Nombre de contacto</span><input className="campo" value={f.contacto} onChange={set("contacto")} autoFocus /></label>
          <label><span className="etiqueta">Despacho o empresa</span><input className="campo" value={f.despacho} onChange={set("despacho")} /></label>
          <label><span className="etiqueta">Correo electrónico</span><input className="campo" type="email" value={f.email} onChange={set("email")} /></label>
          <label><span className="etiqueta">Teléfono (opcional)</span><input className="campo" value={f.telefono} onChange={set("telefono")} /></label>
          <div><span className="etiqueta">País y moneda</span><p className="rounded-xl border border-crema-300 bg-crema px-3 py-2 text-sm">México · MXN</p></div>
          <label className="sm:col-span-2"><span className="etiqueta">Necesidad del despacho (la verá el cliente, opcional)</span>
            <textarea className="campo" rows={2} maxLength={1000} value={f.necesidad} onChange={set("necesidad")} /></label>
          <label className="sm:col-span-2"><span className="etiqueta">Notas internas (nunca las ve el cliente)</span>
            <textarea className="campo" rows={2} maxLength={5000} value={f.notas_internas} onChange={set("notas_internas")} /></label>
          <p className="text-xs text-slate-500 sm:col-span-2">No capture CURP, NSS, datos de expedientes ni documentos jurídicos.</p>
        </div>}

        {paso === 1 && <div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-3">
            {activos.map((p: any) => (
              <button type="button" key={p.id} onClick={() => setE({ paquete_id: p.id, incluidos: e.modulos.slice(0, p.modulos_incluidos) })}
                className={`rounded-2xl border-2 p-4 text-left transition ${e.paquete_id === p.id ? "border-turquesa bg-turquesa-50" : "border-crema-300 hover:border-marino-300"}`} aria-pressed={e.paquete_id === p.id}>
                <div className="font-bold text-marino">{p.nombre}</div>
                <div className="text-lg font-extrabold text-marino">{mxn(p.precio_mensual)} <span className="text-xs font-medium text-slate-500">/mes + IVA</span></div>
                <div className="mt-1 text-xs text-slate-600">{p.modulos_incluidos} módulo(s) · {p.usuarios} usuarios · {p.almacenamiento_gb} GB</div>
              </button>))}
            {!activos.length && <Aviso>No hay paquetes activos. Active uno en «Paquetes y precios».</Aviso>}
          </div>
          <fieldset>
            <legend className="etiqueta">Módulos</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {cat.modulos.map((x: any) => {
                const sel = e.modulos.includes(x.clave);
                const precio = cat.precios.find((p: any) => p.clave === `modulo:${x.clave}`);
                return (
                  <div key={x.clave} className={`rounded-xl border p-3 ${sel ? "border-turquesa/50 bg-white" : "border-crema-300"}`}>
                    <label className="flex items-center gap-2 font-semibold text-marino"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={sel} onChange={() => alternarModulo(x.clave)} />{x.nombre}</label>
                    {sel && <label className="mt-1 flex items-center gap-2 pl-6 text-xs text-slate-600"><input type="checkbox" className="accent-turquesa" checked={e.incluidos.includes(x.clave)} onChange={() => alternarIncluido(x.clave)} />
                      Incluido en el paquete {!e.incluidos.includes(x.clave) && precio && <span>(adicional: {mxn(precio.precio_mensual)}/mes)</span>}</label>}
                  </div>);
              })}
            </div>
          </fieldset>
          <div className="grid gap-3 sm:grid-cols-2">
            <label><span className="etiqueta">Usuarios internos adicionales</span><input className="campo" type="number" min={0} max={1000} value={e.usuarios_extra} onChange={(ev) => setE({ usuarios_extra: Number(ev.target.value) || 0 })} /></label>
            <label><span className="etiqueta">Bloques de almacenamiento adicional</span><input className="campo" type="number" min={0} max={200} value={e.bloques_extra} onChange={(ev) => setE({ bloques_extra: Number(ev.target.value) || 0 })} /></label>
          </div>
          <p className="text-xs text-slate-500">Los clientes invitados al portal no cuentan como usuarios internos. No se cobra por expediente.</p>
          {e.modulos.includes("academia") && <fieldset className="rounded-xl border border-crema-300 p-3">
            <legend className="px-1 text-sm font-semibold text-marino">Nomira Academia</legend>
            <label className="block max-w-xs"><span className="etiqueta">Cursos propios adicionales (al mes)</span>
              <input className="campo" type="number" min={0} max={500} value={e.cursos_extra || 0} onChange={(ev) => setE({ cursos_extra: Number(ev.target.value) || 0 })} /></label>
            {cat.cursos_academia?.length > 0 && <div className="mt-2 space-y-1">
              <span className="etiqueta">Cursos de Nomira con costo (pago único)</span>
              {cat.cursos_academia.map((x: any) => <label key={x.id} className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa"
                checked={(e.cursos_nomira || []).includes(x.id)} onChange={() => setE({ cursos_nomira: (e.cursos_nomira || []).includes(x.id) ? e.cursos_nomira.filter((y: number) => y !== x.id) : [...(e.cursos_nomira || []), x.id] })} />
                {x.titulo} <span className="text-slate-500">· {mxn(x.precio)} + IVA</span></label>)}
            </div>}
            <p className="mt-1 text-xs text-slate-500">Al asignar la cotización pagada, el despacho recibe los cursos y su límite de cursos propios sube.</p>
          </fieldset>}
        </div>}

        {paso === 2 && <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Fecha de emisión</span><input className="campo" type="date" value={e.emision || ""} onChange={(ev) => setE({ emision: ev.target.value })} /></label>
          <label><span className="etiqueta">Vence (fecha y hora)</span><input className="campo" type="datetime-local" value={f.vence_en} onChange={set("vence_en")} /></label>
          <label><span className="etiqueta">Periodicidad</span><select className="campo" value={e.periodicidad} onChange={(ev) => setE({ periodicidad: ev.target.value })}>
            {cat.periodicidades.map((p: any) => <option key={p.clave} value={p.clave}>{p.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Fecha límite de pago (opcional)</span><input className="campo" type="date" value={e.fecha_limite_pago || ""} onChange={(ev) => setE({ fecha_limite_pago: ev.target.value })} /></label>
          <fieldset className="rounded-xl border border-crema-300 p-3 sm:col-span-2">
            <legend className="px-1 text-sm font-semibold text-marino">Descuento autorizado (máximo {Number(conf.descuento_maximo_pct)}%)</legend>
            <div className="grid gap-2 sm:grid-cols-[9rem_8rem_1fr]">
              <select className="campo" value={e.descuento?.tipo || "porcentaje"} onChange={(ev) => setE({ descuento: { ...(e.descuento || {}), tipo: ev.target.value } })}>
                <option value="porcentaje">Porcentaje</option><option value="monto">Monto (MXN)</option></select>
              <input className="campo" inputMode="decimal" placeholder="0" aria-label="Valor del descuento" value={e.descuento?.valor && e.descuento.valor !== "0" ? e.descuento.valor : ""}
                onChange={(ev) => setE({ descuento: ev.target.value ? { tipo: "porcentaje", ...(e.descuento || {}), valor: ev.target.value } : null })} />
              <input className="campo" placeholder="Motivo (obligatorio si hay descuento)" aria-label="Motivo del descuento" value={e.descuento?.motivo || ""}
                onChange={(ev) => setE({ descuento: { tipo: "porcentaje", valor: "0", ...(e.descuento || {}), motivo: ev.target.value } })} />
            </div>
            <p className="mt-1 text-xs text-slate-500">El motivo queda registrado y no aparece en el PDF.</p>
          </fieldset>
          <label className="sm:col-span-2"><span className="etiqueta">Cupón de descuento (opcional)</span>
            <input className="campo font-mono uppercase" placeholder="p. ej. BLACKDAY2026" value={e.cupon || ""} maxLength={40}
              onChange={(ev) => setE({ cupon: ev.target.value.replace(/\s/g, "").toUpperCase() || null })} />
            <span className="mt-0.5 block text-xs text-slate-500">Se valida al calcular. El cliente también puede capturarlo en su propuesta antes de aceptarla.</span></label>
          <fieldset className="rounded-xl border border-crema-300 p-3 sm:col-span-2">
            <legend className="px-1 text-sm font-semibold text-marino">Servicios incluidos (pago único; precio 0 = sin costo)</legend>
            <div className="space-y-2">
              {cat.servicios.map((s: any) => {
                const v = servicio(s.clave);
                return (
                  <div key={s.clave} className="grid items-center gap-2 sm:grid-cols-[13rem_8rem_1fr]">
                    <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={!!v} onChange={() => setServicio(s.clave, v ? null : {})} />{s.nombre}</label>
                    {v && <input className="campo" inputMode="decimal" aria-label={`Precio de ${s.nombre}`} value={v.precio} onChange={(ev) => setServicio(s.clave, { precio: ev.target.value })} />}
                    {v && <input className="campo" placeholder="Descripción breve (opcional)" aria-label={`Descripción de ${s.nombre}`} value={v.descripcion || ""} onChange={(ev) => setServicio(s.clave, { descripcion: ev.target.value })} />}
                  </div>);
              })}
            </div>
          </fieldset>
          <label className="sm:col-span-2"><span className="etiqueta">Condiciones de pago</span><textarea className="campo" rows={2} value={e.condiciones_pago || ""} onChange={(ev) => setE({ condiciones_pago: ev.target.value })} /></label>
          <label className="sm:col-span-2"><span className="etiqueta">Términos de esta cotización</span><textarea className="campo" rows={2} value={e.terminos || ""} onChange={(ev) => setE({ terminos: ev.target.value })} /></label>
          <label className="sm:col-span-2"><span className="etiqueta">Observaciones comerciales</span><textarea className="campo" rows={2} value={e.observaciones || ""} onChange={(ev) => setE({ observaciones: ev.target.value })} /></label>
          <label><span className="etiqueta">Preparada por</span><input className="campo" value={f.preparada_por} onChange={set("preparada_por")} placeholder="Su nombre" /></label>
        </div>}

        {paso === 3 && <div className="space-y-3 text-sm">
          <dl className="grid grid-cols-[10rem_1fr] gap-y-1.5">
            <dt className="text-slate-500">Cliente</dt><dd className="font-semibold text-marino">{f.contacto} · {f.despacho}</dd>
            <dt className="text-slate-500">Correo</dt><dd>{f.email}</dd>
            <dt className="text-slate-500">Paquete</dt><dd>{calc?.paquete.nombre} · {calc?.periodicidad.nombre}</dd>
            <dt className="text-slate-500">Módulos</dt><dd>{calc?.modulos.map((m: any) => `${m.nombre}${m.incluido ? "" : " (adicional)"}`).join(", ")}</dd>
            <dt className="text-slate-500">Vence</dt><dd>{new Date(f.vence_en).toLocaleString("es-MX")}</dd>
            {e.descuento?.motivo && <><dt className="text-slate-500">Motivo del descuento</dt><dd>{e.descuento.motivo} <span className="text-xs text-slate-500">(interno)</span></dd></>}
          </dl>
          <p className="text-slate-600">Al guardar, la cotización queda en <b>borrador</b>. En la siguiente pantalla verá la vista previa del PDF y del correo antes de enviarla.</p>
        </div>}

        <Aviso>{error}</Aviso>
        <div className="mt-5 flex flex-wrap justify-between gap-2">
          <div className="flex gap-2">
            {paso > 0 && <button type="button" className="btn-sec" onClick={() => setPaso(paso - 1)}>← Anterior</button>}
            {onCancelar && <button type="button" className="btn-sec" onClick={onCancelar}>Cancelar</button>}
          </div>
          {paso < 3
            ? <button type="button" className="btn-primario" disabled={!pasoValido[paso]} onClick={() => setPaso(paso + 1)}>Siguiente →</button>
            : <button type="button" className="btn-turquesa" disabled={!calc || guardando} onClick={guardar}>{guardando ? "Guardando…" : cot ? "Guardar cambios" : "Guardar cotización"}</button>}
        </div>
      </section>
      <aside className="tarjeta h-fit p-5 xl:sticky xl:top-6">
        <h2 className="mb-2 font-semibold text-marino">Importe (calculado por el servidor)</h2>
        {errCalc && <Aviso tipo="alerta">{errCalc}</Aviso>}
        <Desglose calc={calc} />
      </aside>
    </div>
  );
}
