"use client";
import { useEffect, useState } from "react";
import { type ClienteBreve, SelectorCliente } from "@/components/clientes";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

export const SEMAFORO: Record<string, { punto: string; caja: string; texto: string }> = {
  rojo: { punto: "bg-red-500", caja: "border-red-200 bg-red-50 text-red-900", texto: "text-red-700" },
  amarillo: { punto: "bg-amber-400", caja: "border-amber-200 bg-amber-50 text-amber-900", texto: "text-amber-700" },
  verde: { punto: "bg-emerald-500", caja: "border-emerald-200 bg-emerald-50 text-emerald-900", texto: "text-emerald-700" },
};

export function Semaforo({ s, chico = false }: { s: any; chico?: boolean }) {
  const c = SEMAFORO[s.color];
  return <span className={`inline-flex items-center gap-1.5 font-semibold ${c.texto} ${chico ? "text-xs" : "text-sm"}`}>
    <span className={`inline-block rounded-full ${c.punto} ${chico ? "h-2.5 w-2.5" : "h-3 w-3"}`} aria-hidden />{s.texto}</span>;
}

export function Barra({ pct }: { pct: number }) {
  return <div className="h-2 w-full overflow-hidden rounded-full bg-crema-200" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
    <div className="h-full rounded-full bg-turquesa transition-all" style={{ width: `${pct}%` }} /></div>;
}

export function useCatalogosEsc() {
  const [c, setC] = useState<any>(null);
  useEffect(() => { api.get("/escrituracion/catalogos").then(setC).catch(() => {}); }, []);
  return c;
}

export const fechaCorta = (iso?: string | null) => iso ? new Date(iso.length === 10 ? iso + "T12:00" : iso).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" }) : "—";
export const fechaHoraCorta = (iso?: string | null) => iso ? new Date(iso).toLocaleString("es-MX", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

type ParteForm = { rol: string; cliente: ClienteBreve | null; nombre: string; tipo: string; email: string; casado: boolean };

/** Alta de expediente: acto, inmueble y partes (desde Clientes o capturadas aquí). */
export function NuevoExpediente({ cat, onCerrar, onListo }: { cat: any; onCerrar: () => void; onListo: (e: any) => void }) {
  const [f, setF] = useState<any>({ acto: "compraventa", titulo: "", inmueble: "", valor_operacion: "", responsable_id: String(cat.yo), cita_firma: "", cita_lugar: "" });
  const nuevaParte = (rol: string): ParteForm => ({ rol, cliente: null, nombre: "", tipo: "fisica", email: "", casado: false });
  const [partes, setPartes] = useState<ParteForm[]>(cat.roles_por_acto.compraventa.map(nuevaParte));
  const [error, setError] = useState("");
  const inmueble = ["compraventa", "compraventa_credito", "donacion", "adjudicacion", "cancelacion_hipoteca"].includes(f.acto);
  function cambiarActo(acto: string) { setF({ ...f, acto }); setPartes(cat.roles_por_acto[acto].map(nuevaParte)); }
  const setParte = (i: number, x: Partial<ParteForm>) => setPartes(partes.map((p, j) => (j === i ? { ...p, ...x } : p)));
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      onListo(await api.post("/escrituracion/expedientes", {
        ...f, inmueble: f.inmueble || null, valor_operacion: f.valor_operacion || null, responsable_id: f.responsable_id ? Number(f.responsable_id) : null,
        cita_firma: f.cita_firma ? new Date(f.cita_firma).toISOString() : null, cita_lugar: f.cita_lugar || null,
        partes: partes.filter((p) => p.cliente || p.nombre.trim()).map((p) => ({ rol: p.rol, cr_cliente_id: p.cliente?.id ?? null, nombre: p.cliente ? null : p.nombre,
          tipo: p.tipo, email: p.cliente ? null : p.email || null, casado: p.casado })),
      }));
    } catch (x: any) { setError(x.message); }
  }
  const c = (k: string) => ({ value: f[k] ?? "", onChange: (e: any) => setF({ ...f, [k]: e.target.value }) });
  return (
    <Modal titulo="Nuevo expediente de escrituración" onCerrar={onCerrar} ancho="max-w-3xl">
      <form className="space-y-4" onSubmit={guardar}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Acto</span><select className="campo" value={f.acto} onChange={(e) => cambiarActo(e.target.value)}>
            {Object.entries(cat.actos).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
          <label><span className="etiqueta">Nombre del expediente</span><input className="campo" required minLength={3} placeholder="Ej. Casa en Av. Juárez 120" {...c("titulo")} /></label>
          {inmueble && <><label className="sm:col-span-2"><span className="etiqueta">Ubicación del inmueble</span><input className="campo" {...c("inmueble")} /></label>
            <label><span className="etiqueta">Valor de la operación (opcional)</span><input className="campo" inputMode="decimal" value={f.valor_operacion} onChange={(e) => setF({ ...f, valor_operacion: e.target.value.replace(/[^\d.]/g, "") })} /></label></>}
          <label><span className="etiqueta">Responsable</span><select className="campo" {...c("responsable_id")}>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Cita de firma (si ya la tiene)</span><input className="campo" type="datetime-local" {...c("cita_firma")} /></label>
        </div>
        <fieldset className="space-y-3 rounded-xl border border-crema-300 p-3"><legend className="etiqueta px-1">Partes</legend>
          {partes.map((p, i) => (
            <div key={i} className="rounded-xl bg-crema/50 p-3">
              <div className="mb-2 flex items-center justify-between gap-2"><select className="campo w-auto" value={p.rol} onChange={(e) => setParte(i, { rol: e.target.value })} aria-label="Rol">
                {Object.entries(cat.roles).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select>
                <button type="button" className="text-xs text-slate-500 underline" onClick={() => setPartes(partes.filter((_, j) => j !== i))}>Quitar</button></div>
              <SelectorCliente valor={p.cliente} onCambio={(x) => setParte(i, { cliente: x })} etiqueta={`${cat.roles[p.rol]}: elegir de Clientes`} />
              {!p.cliente && <div className="mt-2 grid gap-2 sm:grid-cols-3">
                <input className="campo" placeholder="…o escriba el nombre" value={p.nombre} onChange={(e) => setParte(i, { nombre: e.target.value })} aria-label="Nombre de la parte" />
                <input className="campo" type="email" placeholder="Correo (opcional)" value={p.email} onChange={(e) => setParte(i, { email: e.target.value })} aria-label="Correo de la parte" />
                <select className="campo" value={p.tipo} onChange={(e) => setParte(i, { tipo: e.target.value })} aria-label="Tipo de persona"><option value="fisica">Persona física</option><option value="moral">Persona moral</option></select></div>}
              {(p.cliente?.tipo ?? p.tipo) !== "moral" && <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={p.casado} onChange={(e) => setParte(i, { casado: e.target.checked })} /> Casado(a) (se pide acta de matrimonio)</label>}
            </div>))}
          <button type="button" className="text-sm font-semibold text-turquesa-700 underline" onClick={() => setPartes([...partes, nuevaParte("otro")])}>+ Agregar parte</button>
        </fieldset>
        <p className="text-xs text-slate-500">Nomira crea las etapas y la lista de documentos según el acto. Las vigencias son sugeridas: ajústelas a la práctica de su estado.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Crear expediente</button></div>
      </form>
    </Modal>
  );
}
