"use client";
import { useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

export const fechaCorta = (s?: string | null) => s ? new Date(s.length === 10 ? s + "T12:00:00" : s).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" }) : "—";
export const ESTADO_INC: Record<string, [string, string]> = {
  pendiente: ["Por autorizar", "bg-amber-100 text-amber-800"], aprobada: ["Autorizada", "bg-emerald-100 text-emerald-800"],
  rechazada: ["Rechazada", "bg-red-100 text-red-800"], cancelada: ["Cancelada", "bg-slate-100 text-slate-500"],
};
export function Chip({ e }: { e: [string, string] }) { return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${e[1]}`}>{e[0]}</span>; }

function useForm<T extends Record<string, any>>(inicial: T) {
  const [f, setF] = useState<T>(inicial);
  const pon = (k: keyof T) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });
  return { f, setF, pon };
}

async function enviar(setError: (s: string) => void, setEnviando: (b: boolean) => void, fn: () => Promise<any>, onListo: (r: any) => void) {
  setError(""); setEnviando(true);
  try { onListo(await fn()); } catch (e: any) { setError(e.message); } finally { setEnviando(false); }
}

function Botones({ onCerrar, enviando, texto }: { onCerrar: () => void; enviando: boolean; texto: string }) {
  return <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
    <button className="btn-turquesa" disabled={enviando}>{enviando ? "Guardando…" : texto}</button></div>;
}

export function FormEmpleado({ cfg, empleado, empresa, onCerrar, onListo }: { cfg: any; empleado?: any; empresa?: number; onCerrar: () => void; onListo: (r: any) => void }) {
  const { f, pon } = useForm({ empresa_id: String(empleado?.empresa_id ?? empresa ?? cfg.empresas[0]?.id ?? ""), nombre: empleado?.nombre ?? "", puesto: empleado?.puesto ?? "",
    area: empleado?.area ?? "", email: empleado?.email ?? "", telefono: empleado?.telefono ?? "", rfc: empleado?.rfc ?? "", curp: empleado?.curp ?? "", nss: empleado?.nss ?? "",
    fecha_ingreso: empleado?.fecha_ingreso ?? "", tipo_contrato: empleado?.tipo_contrato ?? "indeterminado", salario_diario: empleado?.salario_diario ?? "", notas: empleado?.notas ?? "" });
  const [error, setError] = useState(""); const [enviando, setEnviando] = useState(false);
  const campo = (k: keyof typeof f, t: string, extra: any = {}) => <label className="block"><span className="etiqueta">{t}</span><input className="campo" value={f[k]} onChange={pon(k)} {...extra} /></label>;
  return (
    <Modal titulo={empleado ? "Editar empleado" : "Alta de empleado"} onCerrar={onCerrar} ancho="max-w-3xl">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); enviar(setError, setEnviando, () => {
        const d = { ...f, empresa_id: Number(f.empresa_id), salario_diario: f.salario_diario || "0" };
        return empleado ? api.put(`/rh/empleados/${empleado.id}`, d) : api.post("/rh/empleados", d); }, onListo); }}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block sm:col-span-2"><span className="etiqueta">Empresa (patrón)</span>
            <select className="campo" value={f.empresa_id} onChange={pon("empresa_id")}>{cfg.empresas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}{x.propia ? " (su despacho)" : ""}</option>)}</select></label>
          {campo("nombre", "Nombre completo", { required: true, minLength: 3 })}{campo("puesto", "Puesto")}
          {campo("area", "Área")}{campo("fecha_ingreso", "Fecha de ingreso", { type: "date", required: true })}
          <label className="block"><span className="etiqueta">Contrato</span><select className="campo" value={f.tipo_contrato} onChange={pon("tipo_contrato")}>
            {Object.entries(cfg.contratos).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
          {campo("salario_diario", "Salario diario", { inputMode: "decimal", required: true, placeholder: "$" })}
          {campo("email", "Correo", { type: "email" })}{campo("telefono", "Celular (WhatsApp)", { type: "tel" })}
          {campo("rfc", "RFC", { maxLength: 13 })}{campo("curp", "CURP", { maxLength: 18 })}{campo("nss", "NSS (IMSS)", { inputMode: "numeric", maxLength: 11 })}
        </div>
        <label className="block"><span className="etiqueta">Notas internas</span><textarea className="campo" value={f.notas} onChange={pon("notas")} maxLength={4000} /></label>
        <Aviso>{error}</Aviso><Botones onCerrar={onCerrar} enviando={enviando} texto={empleado ? "Guardar cambios" : "Dar de alta"} />
      </form>
    </Modal>
  );
}

export function FormEmpresa({ cfg, empresa, clientes, onCerrar, onListo }: { cfg: any; empresa?: any; clientes: any[]; onCerrar: () => void; onListo: (r: any) => void }) {
  const { f, setF, pon } = useForm({ nombre: empresa?.nombre ?? "", cliente_id: empresa?.cliente_id ? String(empresa.cliente_id) : "", rfc: empresa?.rfc ?? "",
    registro_patronal: empresa?.registro_patronal ?? "", periodicidad: empresa?.periodicidad ?? "quincenal", activa: empresa?.activa ?? true });
  const [error, setError] = useState(""); const [enviando, setEnviando] = useState(false);
  return (
    <Modal titulo={empresa ? "Editar empresa" : "Agregar empresa cliente"} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); enviar(setError, setEnviando, () => {
        const d = { ...f, cliente_id: f.cliente_id ? Number(f.cliente_id) : null };
        return empresa ? api.put(`/rh/empresas/${empresa.id}`, d) : api.post("/rh/empresas", d); }, onListo); }}>
        {!empresa?.propia && <label className="block"><span className="etiqueta">Ligar a un cliente del despacho (opcional)</span>
          <select className="campo" value={f.cliente_id} onChange={(e) => { const c = clientes.find((x) => String(x.id) === e.target.value);
            setF({ ...f, cliente_id: e.target.value, nombre: c ? c.nombre : f.nombre, rfc: c?.rfc || f.rfc }); }}>
            <option value="">— Sin ligar —</option>{clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></label>}
        <label className="block"><span className="etiqueta">Nombre o razón social</span><input className="campo" value={f.nombre} onChange={pon("nombre")} required minLength={2} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">RFC</span><input className="campo" value={f.rfc} onChange={pon("rfc")} maxLength={13} /></label>
          <label className="block"><span className="etiqueta">Registro patronal IMSS</span><input className="campo" value={f.registro_patronal} onChange={pon("registro_patronal")} maxLength={20} /></label>
          <label className="block"><span className="etiqueta">Se paga</span><select className="campo" value={f.periodicidad} onChange={pon("periodicidad")}>
            {Object.entries(cfg.periodicidades).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
        </div>
        <Aviso>{error}</Aviso><Botones onCerrar={onCerrar} enviando={enviando} texto="Guardar" />
      </form>
    </Modal>
  );
}

export function FormIncidencia({ cfg, empleado, onCerrar, onListo }: { cfg: any; empleado: any; onCerrar: () => void; onListo: (r: any) => void }) {
  const { f, pon } = useForm({ tipo: "falta", desde: "", hasta: "", dias: "", motivo: "" });
  const [error, setError] = useState(""); const [enviando, setEnviando] = useState(false);
  return (
    <Modal titulo={`Registrar incidencia de ${empleado.nombre}`} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); enviar(setError, setEnviando, () => api.post(`/rh/empleados/${empleado.id}/incidencias`,
        { ...f, hasta: f.hasta || f.desde, dias: f.dias || null }), onListo); }}>
        <label className="block"><span className="etiqueta">¿Qué pasó?</span><select className="campo" value={f.tipo} onChange={pon("tipo")}>
          {Object.entries(cfg.tipos).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block"><span className="etiqueta">Desde</span><input className="campo" type="date" value={f.desde} onChange={pon("desde")} required /></label>
          <label className="block"><span className="etiqueta">Hasta</span><input className="campo" type="date" value={f.hasta} onChange={pon("hasta")} min={f.desde} /></label>
          <label className="block"><span className="etiqueta">Días (opcional)</span><input className="campo" inputMode="decimal" value={f.dias} onChange={pon("dias")} placeholder="Automático" /></label>
        </div>
        <label className="block"><span className="etiqueta">Motivo o nota</span><input className="campo" value={f.motivo} onChange={pon("motivo")} maxLength={500} /></label>
        <p className="text-xs text-slate-500">Las faltas y los permisos sin goce se descuentan solos en la nómina; las vacaciones restan días del saldo y generan la prima vacacional.</p>
        <Aviso>{error}</Aviso><Botones onCerrar={onCerrar} enviando={enviando} texto="Registrar" />
      </form>
    </Modal>
  );
}

export function FormAviso({ cfg, aviso, onCerrar, onListo }: { cfg: any; aviso?: any; onCerrar: () => void; onListo: (r: any) => void }) {
  const { f, pon } = useForm({ titulo: aviso?.titulo ?? "", cuerpo: aviso?.cuerpo ?? "", empresa_id: aviso?.empresa_id ? String(aviso.empresa_id) : "",
    fijado: aviso?.fijado ?? false, requiere_acuse: aviso?.requiere_acuse ?? false, vigente_hasta: aviso?.vigente_hasta ?? "" });
  const [error, setError] = useState(""); const [enviando, setEnviando] = useState(false);
  return (
    <Modal titulo={aviso ? "Editar aviso" : "Nuevo aviso al personal"} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); enviar(setError, setEnviando, () => {
        const d = { ...f, empresa_id: f.empresa_id ? Number(f.empresa_id) : null, vigente_hasta: f.vigente_hasta || null };
        return aviso ? api.put(`/rh/avisos/${aviso.id}`, d) : api.post("/rh/avisos", d); }, onListo); }}>
        <label className="block"><span className="etiqueta">Título</span><input className="campo" value={f.titulo} onChange={pon("titulo")} required minLength={3} maxLength={200} placeholder="Ej. Día inhábil el 2 de noviembre" /></label>
        <label className="block"><span className="etiqueta">Mensaje</span><textarea className="campo min-h-32" value={f.cuerpo} onChange={pon("cuerpo")} required minLength={3} maxLength={8000} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">¿Para quién?</span><select className="campo" value={f.empresa_id} onChange={pon("empresa_id")}>
            <option value="">Todo el personal de todas las empresas</option>{cfg.empresas.map((x: any) => <option key={x.id} value={x.id}>Solo {x.nombre}</option>)}</select></label>
          <label className="block"><span className="etiqueta">Mostrar hasta (opcional)</span><input className="campo" type="date" value={f.vigente_hasta} onChange={pon("vigente_hasta")} /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.requiere_acuse} onChange={pon("requiere_acuse")} /> Pedir que confirmen que lo leyeron (acuse de lectura)</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.fijado} onChange={pon("fijado")} /> Fijar hasta arriba</label>
        <Aviso>{error}</Aviso><Botones onCerrar={onCerrar} enviando={enviando} texto={aviso ? "Guardar" : "Publicar aviso"} />
      </form>
    </Modal>
  );
}

export function FormPeriodo({ cfg, onCerrar, onListo }: { cfg: any; onCerrar: () => void; onListo: (r: any) => void }) {
  const hoy = new Date();
  const q1 = hoy.getDate() <= 15;
  const iso = (d: Date) => d.toLocaleDateString("en-CA");
  const ini = new Date(hoy.getFullYear(), hoy.getMonth(), q1 ? 1 : 16);
  const fin = q1 ? new Date(hoy.getFullYear(), hoy.getMonth(), 15) : new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);
  const { f, pon } = useForm({ empresa_id: String(cfg.empresas[0]?.id ?? ""), inicio: iso(ini), fin: iso(fin), fecha_pago: iso(fin) });
  const [error, setError] = useState(""); const [enviando, setEnviando] = useState(false);
  return (
    <Modal titulo="Nuevo periodo de nómina" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); enviar(setError, setEnviando, () => api.post("/rh/periodos", { ...f, empresa_id: Number(f.empresa_id) }), onListo); }}>
        <label className="block"><span className="etiqueta">Empresa</span><select className="campo" value={f.empresa_id} onChange={pon("empresa_id")}>
          {cfg.empresas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre} · {cfg.periodicidades[x.periodicidad]}</option>)}</select></label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block"><span className="etiqueta">Del</span><input className="campo" type="date" value={f.inicio} onChange={pon("inicio")} required /></label>
          <label className="block"><span className="etiqueta">Al</span><input className="campo" type="date" value={f.fin} onChange={pon("fin")} required /></label>
          <label className="block"><span className="etiqueta">Fecha de pago</span><input className="campo" type="date" value={f.fecha_pago} onChange={pon("fecha_pago")} required /></label>
        </div>
        <p className="text-xs text-slate-500">Nomira arma un recibo por empleado con su sueldo, descuenta faltas y permisos sin goce, y agrega la prima vacacional. Usted ajusta bonos y retenciones (ISR, IMSS) con los datos de su contador.</p>
        <Aviso>{error}</Aviso><Botones onCerrar={onCerrar} enviando={enviando} texto="Armar nómina" />
      </form>
    </Modal>
  );
}

export function AccesoPortal({ empleado, onCerrar }: { empleado: any; onCerrar: () => void }) {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState(""); const [ok, setOk] = useState("");
  const texto = r ? `Hola ${empleado.nombre.split(" ")[0]}, este es tu acceso al portal de Recursos Humanos: ${r.url}\nTu NIP es ${r.nip}. No lo compartas.` : "";
  return (
    <Modal titulo={`Portal de ${empleado.nombre}`} onCerrar={onCerrar}>
      {!r ? <div className="space-y-3 text-sm">
        <p>En su portal el empleado ve los avisos (y confirma que los leyó), pide vacaciones o permisos, descarga sus recibos y sube sus documentos desde el celular.</p>
        {empleado.portal && <Aviso tipo="info">Ya tiene acceso. Si genera uno nuevo, el enlace y el NIP anteriores dejan de funcionar.</Aviso>}
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" onClick={async () => { try { setR(await api.post(`/rh/empleados/${empleado.id}/portal`, {})); } catch (e: any) { setError(e.message); } }}>
            {empleado.portal ? "Generar acceso nuevo" : "Generar acceso"}</button></div>
      </div> : <div className="space-y-3 text-sm">
        <Aviso tipo="ok">Acceso listo. Cópielo ahora: el NIP no se vuelve a mostrar.</Aviso>
        <p className="break-all rounded-lg bg-crema/60 p-3"><b>Enlace:</b> {r.url}<br /><b>NIP:</b> <span className="font-mono text-lg tracking-widest">{r.nip}</span></p>
        <Aviso tipo="ok">{ok}</Aviso>
        <div className="flex flex-wrap justify-end gap-2">
          <button className="btn-sec" onClick={async () => { try { await navigator.clipboard.writeText(texto); setOk("Copiado."); } catch { setOk(""); } }}>Copiar mensaje</button>
          {empleado.telefono && <a className="btn-sec" target="_blank" rel="noopener noreferrer" href={`https://wa.me/${empleado.telefono.replace(/\D/g, "").replace(/^(\d{10})$/, "52$1")}?text=${encodeURIComponent(texto)}`}>Mandar por WhatsApp</a>}
          <button className="btn-turquesa" onClick={onCerrar}>Listo</button></div>
      </div>}
    </Modal>
  );
}
