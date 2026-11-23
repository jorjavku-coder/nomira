"use client";
import Link from "next/link";
import BotonAyuda from "@/components/BotonAyuda";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, fechaHora } from "@/lib/api";

/** Marco de Nomira AFORE: submenú del módulo y aviso de alcance. */
export function AforeShell({ children }: { children: React.ReactNode }) {
  const ruta = usePathname();
  const enlaces: [string, string, boolean][] = [
    ["/afore", "Resumen", ruta === "/afore"], ["/afore/casos", "Casos AFORE", ruta.startsWith("/afore/casos")],
    ["/afore/clientes", "Clientes", ruta.startsWith("/afore/clientes")], ["/afore/mensajes", "Mensajes", ruta.startsWith("/afore/mensajes")],
    ["/afore/catalogos", "Catálogos y plantillas", ruta.startsWith("/afore/catalogos")], ["/afore/configuracion", "Configuración", ruta.startsWith("/afore/configuracion")],
  ];
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">Nomira AFORE</p>
          <p className="text-xs text-slate-500">Casos de AFORE (Administradora de Fondos para el Retiro) y del SAR (Sistema de Ahorro para el Retiro).</p>
        </div>
        <BotonAyuda modulo="afore" />
      </div>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-crema-300" aria-label="Nomira AFORE">
        {enlaces.map(([href, t, activo]) => (
          <Link key={href} href={href} aria-current={activo ? "page" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold ${activo ? "border-turquesa text-marino" : "border-transparent text-slate-500 hover:text-marino"}`}>{t}</Link>
        ))}
      </nav>
      {children}
      <p className="mt-10 text-center text-xs text-slate-400">Nomira organiza información y procesos. No decide derechos, beneficiarios, acciones legales ni resultados: esa decisión es siempre del abogado.</p>
    </Shell>
  );
}

let cache: any = null;
/** Catálogos del módulo (tipos de problema, estados, responsables…), una sola vez por página. */
export function useCatalogos(): any {
  const [c, setC] = useState<any>(cache);
  useEffect(() => { if (!cache) api.get("/afore/catalogos").then((x) => { cache = x; setC(x); }).catch(() => {}); }, []);
  return c;
}
export const recargarCatalogos = () => { cache = null; };

export function Pastilla({ clase = "bg-slate-100 text-slate-700", children }: { clase?: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${clase}`}>{children}</span>;
}

export const COLOR_CASO: Record<string, string> = {
  borrador: "bg-slate-100 text-slate-700", abierto: "bg-turquesa-50 text-turquesa-700", esperando: "bg-amber-100 text-amber-800",
  pausado: "bg-slate-200 text-slate-600", cerrado: "bg-marino-50 text-marino",
};
export const COLOR_REQ: Record<string, string> = {
  no_solicitado: "bg-slate-100 text-slate-600", solicitado: "bg-amber-100 text-amber-800", recibido: "bg-sky-100 text-sky-800",
  por_revisar: "bg-sky-100 text-sky-800", aceptado: "bg-emerald-100 text-emerald-800", requiere_correccion: "bg-red-100 text-red-800",
  no_aplica: "bg-slate-100 text-slate-400",
};
export const COLOR_MSJ: Record<string, string> = {
  borrador: "bg-slate-100 text-slate-700", esperando_aprobacion: "bg-amber-100 text-amber-800", enviado: "bg-sky-100 text-sky-800",
  entregado: "bg-emerald-100 text-emerald-800", leido: "bg-emerald-100 text-emerald-800", fallido: "bg-red-100 text-red-800",
  cancelado: "bg-slate-200 text-slate-500", recibido: "bg-violet-100 text-violet-800", por_asignar: "bg-violet-100 text-violet-800",
};

/** Un dato del caso con su estado: informado, «No lo sé», «Pendiente de confirmar» o «No aplica». */
export function CampoDato({ etiqueta, valor, onCambio, lista, monto, estados }: {
  etiqueta: string; valor: { valor?: string | null; estado?: string } | undefined; onCambio: (v: { valor: string | null; estado: string }) => void;
  lista?: string[]; monto?: boolean; estados: Record<string, string>;
}) {
  const estado = valor?.estado || "pendiente";
  const id = etiqueta.replace(/\W/g, "");
  return (
    <div className="rounded-xl border border-crema-300 p-3">
      <span className="etiqueta">{etiqueta}</span>
      <div className="flex flex-wrap gap-2">
        <input className="campo min-w-0 flex-1" list={lista ? `l-${id}` : undefined} inputMode={monto ? "decimal" : undefined}
          placeholder={estado === "informado" || !valor?.estado ? (monto ? "0.00 (dato informado)" : "Escriba") : estados[estado]}
          value={estado === "informado" ? valor?.valor || "" : ""} onChange={(e) => onCambio({ valor: e.target.value, estado: "informado" })} />
        {lista && <datalist id={`l-${id}`}>{lista.map((x) => <option key={x} value={x} />)}</datalist>}
        <select className="campo w-auto" value={estado} aria-label={`Estado de ${etiqueta}`}
          onChange={(e) => onCambio({ valor: e.target.value === "informado" ? valor?.valor || "" : null, estado: e.target.value })}>
          {Object.entries(estados).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
        </select>
      </div>
    </div>
  );
}

export const mxnTexto = (v?: string | null) => (v ? Number(v).toLocaleString("es-MX", { style: "currency", currency: "MXN" }) : "—");

/** Mensaje al cliente: estado real, qué falta para enviarlo y aprobación humana. */
export function TarjetaMensaje({ x, puedeAprobar, editor, accion }: any) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(x.texto);
  return (
    <div className="tarjeta p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Pastilla clase={COLOR_MSJ[x.estado]}>{x.estado_texto}</Pastilla>
        <span className="text-xs font-semibold uppercase text-slate-500">{x.canal === "whatsapp" ? "WhatsApp" : "Correo"} · {x.direccion === "entrante" ? "recibido" : "para el cliente"}</span>
        {x.cliente && <span className="text-xs text-slate-600">{x.cliente}</span>}
        <span className="ml-auto text-xs text-slate-400">{fechaHora(x.creado_en)}</span>
      </div>
      {editando ? <textarea className="campo mt-2" rows={3} maxLength={1000} value={texto} onChange={(e) => setTexto(e.target.value)} />
        : <p className="mt-2 whitespace-pre-line text-slate-800">{x.texto}</p>}
      {x.motivo && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900"><b>Falta para poder enviarlo:</b> {x.motivo}</p>}
      {x.error && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800"><b>Error del proveedor:</b> {x.error}</p>}
      <p className="mt-1 text-xs text-slate-500">{[x.aprobado_por && `Aprobó ${x.aprobado_por}`, x.enviado_en && `enviado ${fechaHora(x.enviado_en)}`, x.entregado_en && `entregado ${fechaHora(x.entregado_en)}`, x.leido_en && `leído ${fechaHora(x.leido_en)}`].filter(Boolean).join(" · ")}</p>
      {editor && x.direccion === "saliente" && ["borrador", "esperando_aprobacion", "fallido"].includes(x.estado) && (
        <div className="mt-2 flex flex-wrap gap-2">
          {editando ? <button className="btn-primario" onClick={async () => { const r = await accion(() => api.patch(`/afore/mensajes/${x.id}`, { texto }), "Texto actualizado."); if (r) setEditando(false); }}>Guardar texto</button>
            : <button className="btn-sec" onClick={() => setEditando(true)}>Editar texto</button>}
          {puedeAprobar && x.estado === "esperando_aprobacion" && <button className="btn-turquesa" onClick={() => accion(() => api.post(`/afore/mensajes/${x.id}/aprobar`), "Mensaje aprobado.")}>Aprobar y enviar</button>}
          {puedeAprobar && x.estado === "fallido" && <button className="btn-turquesa" onClick={() => accion(() => api.post(`/afore/mensajes/${x.id}/reintentar`), "Reintento realizado.")}>Reintentar</button>}
          {x.estado === "borrador" && <button className="btn-sec" onClick={() => accion(() => api.post(`/afore/mensajes/${x.id}/revisar`), "Revisado.")}>Volver a revisar qué falta</button>}
          <button className="btn-sec" onClick={() => accion(() => api.post(`/afore/mensajes/${x.id}/cancelar`), "Mensaje cancelado.")}>Cancelar</button>
          {!puedeAprobar && x.estado === "esperando_aprobacion" && <span className="self-center text-xs text-slate-500">Lo aprueba un administrador o el abogado responsable.</span>}
        </div>)}
    </div>
  );
}

