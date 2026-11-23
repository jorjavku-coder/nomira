"use client";
import { useEffect, useState } from "react";
import { type ClienteBreve, SelectorCliente } from "@/components/clientes";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

export const ENTIDADES = ["Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua",
  "Ciudad de México", "Coahuila", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán",
  "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora",
  "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas"];
export const TIPOS_CASO = ["Laboral", "Civil", "Mercantil", "Familiar", "Administrativo", "Fiscal", "Penal", "Agrario", "Seguridad social"];

/** Formulario de datos del asunto (alta y edición). Ningún campo jurídico es obligatorio salvo el nombre. */
export function FormAsunto({ inicial, onGuardar, onCerrar, titulo }: {
  inicial?: any; titulo: string; onCerrar: () => void; onGuardar: (datos: any) => Promise<any>;
}) {
  const [f, setF] = useState({
    nombre: inicial?.nombre || "", cliente: inicial?.cliente || "", tipo_caso: inicial?.tipo_caso || "",
    jurisdiccion: inicial?.jurisdiccion || "", identificador_interno: inicial?.identificador_interno || "",
    responsable_id: inicial?.responsable_id ? String(inicial.responsable_id) : "", notas: inicial?.notas || "",
    ambito: inicial?.ambito || "", entidad_federativa: inicial?.entidad_federativa || "", municipio_distrito: inicial?.municipio_distrito || "",
    organo: inicial?.organo || "", expediente_judicial: inicial?.expediente_judicial || "",
  });
  const entidadInvalida = !!f.entidad_federativa && !ENTIDADES.includes(f.entidad_federativa);
  const [campos, setCampos] = useState<[string, string][]>(Object.entries(inicial?.campos || {}) as [string, string][]);
  const [cliente, setCliente] = useState<ClienteBreve | null>(inicial?.cr_cliente_id ? { id: inicial.cr_cliente_id, nombre: inicial.cliente || "Cliente" } : null);
  const [responsables, setResponsables] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => { api.get("/evidencia/responsables").then(setResponsables).catch(() => {}); }, []);
  const cambiar = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (entidadInvalida) { setError("Elija la entidad federativa de la lista."); return; }
    setError(""); setGuardando(true);
    try {
      await onGuardar({
        ...f, responsable_id: f.responsable_id ? Number(f.responsable_id) : null, ambito: f.ambito || null,
        cr_cliente_id: cliente?.id ?? null, cliente: cliente ? cliente.nombre : f.cliente,
        entidad_federativa: f.ambito === "local" ? f.entidad_federativa || null : null,
        campos: Object.fromEntries(campos.filter(([k, v]) => k.trim() && v.trim())),
      });
    } catch (err: any) { setError(err.message); }
    setGuardando(false);
  }
  return (
    <Modal titulo={titulo} onCerrar={onCerrar} ancho="max-w-2xl">
      <form onSubmit={enviar} className="space-y-3">
        <label className="block"><span className="etiqueta">Nombre del asunto</span>
          <input className="campo" required minLength={2} maxLength={200} value={f.nombre} onChange={cambiar("nombre")} placeholder="p. ej. Pérez vs. Empresa SA" autoFocus /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2"><SelectorCliente valor={cliente} onCambio={setCliente} etiqueta="Cliente (de su directorio)" />
            {!cliente && f.cliente && <p className="mt-1 text-xs text-slate-500">Capturado antes como texto: «{f.cliente}». Elíjalo del directorio para ligarlo.</p>}</div>
          <label className="block"><span className="etiqueta">Tipo de caso</span>
            <input className="campo" list="tipos-caso" maxLength={120} value={f.tipo_caso} onChange={cambiar("tipo_caso")} placeholder="Escriba o elija" />
            <datalist id="tipos-caso">{TIPOS_CASO.map((t) => <option key={t} value={t} />)}</datalist></label>
          <label className="block sm:col-span-2"><span className="etiqueta">Identificador interno del despacho</span><input className="campo" maxLength={80} value={f.identificador_interno} onChange={cambiar("identificador_interno")} placeholder="Número de control del despacho" /></label>
        </div>
        <fieldset className="rounded-xl border border-crema-300 p-3">
          <legend className="etiqueta px-1">Jurisdicción (todo opcional)</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block"><span className="etiqueta">Ámbito</span>
              <select className="campo" value={f.ambito} onChange={cambiar("ambito")}>
                <option value="">Sin indicar</option><option value="federal">Federal</option><option value="local">Local</option>
              </select></label>
            {f.ambito === "local" && (
              <label className="block"><span className="etiqueta">Entidad federativa</span>
                <input className={`campo ${entidadInvalida ? "border-red-400" : ""}`} list="entidades" value={f.entidad_federativa} onChange={cambiar("entidad_federativa")} placeholder="Escriba para buscar" />
                <datalist id="entidades">{ENTIDADES.map((e) => <option key={e} value={e} />)}</datalist>
                {entidadInvalida && <span className="text-xs text-red-700">Elija una de las 32 entidades.</span>}</label>
            )}
            <label className="block"><span className="etiqueta">Municipio o distrito judicial</span><input className="campo" maxLength={160} value={f.municipio_distrito} onChange={cambiar("municipio_distrito")} /></label>
            <label className="block"><span className="etiqueta">Juzgado, tribunal u órgano</span><input className="campo" maxLength={200} value={f.organo} onChange={cambiar("organo")} placeholder="p. ej. Juzgado Tercero Familiar" /></label>
            <label className="block"><span className="etiqueta">Número de expediente judicial</span><input className="campo" maxLength={80} value={f.expediente_judicial} onChange={cambiar("expediente_judicial")} placeholder="p. ej. 123/2026" /></label>
            {(inicial?.jurisdiccion || f.jurisdiccion) && (
              <label className="block"><span className="etiqueta">Jurisdicción (texto capturado antes)</span><input className="campo" maxLength={160} value={f.jurisdiccion} onChange={cambiar("jurisdiccion")} />
                <span className="text-xs text-slate-500">Se conserva tal cual; puede pasarlo a los campos de arriba.</span></label>
            )}
          </div>
        </fieldset>
        <label className="block"><span className="etiqueta">Responsable</span>
          <select className="campo" value={f.responsable_id} onChange={cambiar("responsable_id")}>
            <option value="">Sin asignar</option>
            {responsables.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
          </select></label>
        <fieldset>
          <legend className="etiqueta">Campos adicionales (opcional)</legend>
          <div className="space-y-2">
            {campos.map(([k, v], i) => (
              <div key={i} className="flex gap-2">
                <input className="campo" placeholder="Campo (p. ej. Contraparte)" maxLength={60} value={k}
                  onChange={(e) => setCampos(campos.map((c, j) => (j === i ? [e.target.value, c[1]] : c)))} aria-label="Nombre del campo" />
                <input className="campo" placeholder="Valor" maxLength={300} value={v}
                  onChange={(e) => setCampos(campos.map((c, j) => (j === i ? [c[0], e.target.value] : c)))} aria-label="Valor del campo" />
                <button type="button" className="btn-sec" aria-label="Quitar campo" onClick={() => setCampos(campos.filter((_, j) => j !== i))}>✕</button>
              </div>
            ))}
            {campos.length < 20 && <button type="button" className="text-sm font-semibold text-turquesa-700 hover:underline" onClick={() => setCampos([...campos, ["", ""]])}>+ Agregar campo</button>}
          </div>
        </fieldset>
        <label className="block"><span className="etiqueta">Notas</span><textarea className="campo" rows={3} maxLength={5000} value={f.notas} onChange={cambiar("notas")} /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
        </div>
      </form>
    </Modal>
  );
}

