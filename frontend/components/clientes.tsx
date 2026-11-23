"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

export type ClienteBreve = { id: number; nombre: string; rfc?: string | null; email?: string | null; telefono?: string | null; tipo?: string };

/** Selector del directorio de Clientes para usar dentro de cualquier módulo. */
export function SelectorCliente({ valor, onCambio, etiqueta = "Cliente", permitirNuevo = true }: {
  valor: ClienteBreve | null; onCambio: (c: ClienteBreve | null) => void; etiqueta?: string; permitirNuevo?: boolean;
}) {
  const [q, setQ] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [lista, setLista] = useState<ClienteBreve[]>([]);
  const [nuevo, setNuevo] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const t = setTimeout(() => api.get(`/clientes/buscar?q=${encodeURIComponent(q)}`).then(setLista).catch(() => setLista([])), 200);
    return () => clearTimeout(t);
  }, [q, abierto]);
  useEffect(() => {
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false); };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, []);
  return (
    <div className="block" ref={caja}>
      <span className="etiqueta">{etiqueta}</span>
      {valor ? (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-turquesa/40 bg-turquesa-50 px-3 py-2 text-sm">
          <span><span className="font-semibold text-marino">{valor.nombre}</span>{valor.rfc && <span className="ml-2 font-mono text-xs text-slate-500">{valor.rfc}</span>}</span>
          <button type="button" className="text-xs font-semibold text-slate-500 underline" onClick={() => { onCambio(null); setQ(""); }}>Cambiar</button>
        </div>
      ) : (
        <div className="relative">
          <input className="campo" placeholder="Buscar en Clientes por nombre, RFC o correo…" value={q} onFocus={() => setAbierto(true)}
            onChange={(e) => { setQ(e.target.value); setAbierto(true); }} aria-label={`${etiqueta}: buscar en Clientes`} />
          {abierto && <ul className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-xl border border-crema-300 bg-white py-1 shadow-xl" role="listbox">
            {lista.map((c) => <li key={c.id}><button type="button" role="option" aria-selected="false" className="block w-full px-3 py-2 text-left text-sm hover:bg-crema"
              onClick={() => { onCambio(c); setAbierto(false); }}>
              <span className="font-semibold text-marino">{c.nombre}</span>
              <span className="ml-2 text-xs text-slate-500">{[c.rfc, c.email].filter(Boolean).join(" · ")}</span></button></li>)}
            {!lista.length && <li className="px-3 py-2 text-sm text-slate-500">{q ? "No hay clientes con ese dato." : "Aún no hay clientes en el directorio."}</li>}
            {permitirNuevo && <li className="border-t border-crema-200"><button type="button" className="block w-full px-3 py-2 text-left text-sm font-semibold text-turquesa-700 hover:bg-crema"
              onClick={() => { setNuevo(true); setAbierto(false); }}>+ Dar de alta «{q || "nuevo cliente"}» en Clientes</button></li>}
          </ul>}
        </div>
      )}
      {nuevo && <FormCliente inicial={{ nombre: q }} onCerrar={() => setNuevo(false)} onGuardado={(c) => { setNuevo(false); onCambio(c); }} />}
    </div>
  );
}

const VACIO = { tipo: "fisica", nombre: "", rfc: "", curp: "", email: "", telefono: "", domicilio: "", codigo_postal: "", regimen_fiscal: "", contacto: "", notas: "", etiquetas: "" };

/** Alta o edición de un cliente. En el alta se puede subir la Constancia de Situación Fiscal para llenar los datos. */
export function FormCliente({ cliente, inicial, onCerrar, onGuardado }: { cliente?: any; inicial?: any; onCerrar: () => void; onGuardado: (c: any) => void }) {
  const [f, setF] = useState<any>(() => cliente ? { ...VACIO, ...Object.fromEntries(Object.entries(cliente).map(([k, v]) => [k, v ?? ""])), curp: "", etiquetas: (cliente.etiquetas || []).join(", ") }
    : { ...VACIO, ...(inicial || {}) });
  const [error, setError] = useState("");
  const [leido, setLeido] = useState<string[] | null>(null);
  const [leyendo, setLeyendo] = useState(false);
  const [duplicado, setDuplicado] = useState("");
  const [csf, setCsf] = useState<File | null>(null);
  const campo = (k: string) => ({ value: f[k] ?? "", onChange: (e: any) => setF({ ...f, [k]: e.target.value }) });
  async function leer(archivo: File) {
    setError(""); setLeyendo(true);
    try {
      const d = new FormData(); d.append("archivo", archivo);
      const r = await api.subir("/clientes/leer-constancia", d);
      const nuevos = Object.fromEntries(Object.entries(r.datos).filter(([, v]) => v));
      setF({ ...f, ...nuevos }); setLeido(r.encontrados); setCsf(archivo);
    } catch (e: any) { setError(e.message); } finally { setLeyendo(false); }
  }
  async function guardar(e: React.FormEvent, forzar = false) {
    e.preventDefault(); setError(""); setDuplicado("");
    const cuerpo = { ...f, etiquetas: String(f.etiquetas || "").split(",").map((t: string) => t.trim()).filter(Boolean), origen: csf ? "constancia" : "manual",
                     responsable_id: f.responsable_id || null };
    for (const k of ["rfc", "curp", "email", "telefono", "domicilio", "codigo_postal", "regimen_fiscal", "contacto", "notas"]) if (!cuerpo[k]) cuerpo[k] = null;
    try {
      const r = cliente ? await api.put(`/clientes/${cliente.id}`, cuerpo) : await api.post(`/clientes${forzar ? "?permitir_duplicado=true" : ""}`, cuerpo);
      if (!cliente && csf) { const d = new FormData(); d.append("archivo", new File([csf], "constancia-situacion-fiscal.pdf", { type: "application/pdf" })); d.append("tipo", "constancia"); d.append("nombre", "Constancia de situación fiscal"); await api.subir(`/clientes/${r.id}/documentos`, d).catch(() => {}); }
      onGuardado(r);
    } catch (e: any) { if (!cliente && /Ya existe/.test(e.message)) setDuplicado(e.message); else setError(e.message); }
  }
  return (
    <Modal titulo={cliente ? "Editar cliente" : "Nuevo cliente"} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-3" onSubmit={guardar}>
        {!cliente && <label className="flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed border-turquesa/50 bg-turquesa-50/60 p-3 text-sm">
          <span className="text-2xl" aria-hidden>📄</span>
          <span className="flex-1"><b className="text-marino">{leyendo ? "Leyendo la constancia…" : "¿Tiene su Constancia de Situación Fiscal?"}</b><br />
            <span className="text-slate-600">Súbala en PDF y Nomira llena los datos por usted. La guardamos en los documentos del cliente.</span></span>
          <input type="file" accept="application/pdf" className="sr-only" aria-label="Subir constancia de situación fiscal" onChange={(e) => e.target.files?.[0] && leer(e.target.files[0])} />
          <span className="btn-sec whitespace-nowrap">Subir PDF</span>
        </label>}
        {leido && <Aviso tipo="ok">Leímos de la constancia: {leido.map((k) => ({ nombre: "nombre", rfc: "RFC", curp: "CURP", domicilio: "domicilio", codigo_postal: "CP", regimen_fiscal: "régimen", email: "correo" } as any)[k] || k).join(", ")}. Revise que todo esté bien antes de guardar.</Aviso>}
        <div className="flex gap-4 text-sm">{[["fisica", "Persona física"], ["moral", "Persona moral (empresa)"]].map(([v, t]) =>
          <label key={v} className="flex items-center gap-2"><input type="radio" name="tipo" checked={f.tipo === v} onChange={() => setF({ ...f, tipo: v })} /> {t}</label>)}</div>
        <label className="block"><span className="etiqueta">{f.tipo === "moral" ? "Razón social" : "Nombre completo"}</span><input className="campo" required minLength={2} {...campo("nombre")} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">RFC</span><input className="campo font-mono uppercase" maxLength={13} {...campo("rfc")} /></label>
          {f.tipo === "fisica" && <label><span className="etiqueta">CURP {cliente?.curp_pista && <span className="normal-case text-slate-400">(guardada: {cliente.curp_pista}; escriba solo para cambiarla)</span>}</span>
            <input className="campo font-mono uppercase" maxLength={18} {...campo("curp")} /></label>}
          <label><span className="etiqueta">Correo</span><input className="campo" type="email" {...campo("email")} /></label>
          <label><span className="etiqueta">Teléfono / WhatsApp</span><input className="campo" inputMode="tel" {...campo("telefono")} /></label>
          {f.tipo === "moral" && <label><span className="etiqueta">Persona de contacto</span><input className="campo" {...campo("contacto")} /></label>}
        </div>
        <details className="rounded-xl border border-crema-300 p-3" open={!!(f.domicilio || f.regimen_fiscal)}>
          <summary className="cursor-pointer text-sm font-semibold text-marino">Domicilio y datos fiscales</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_8rem]">
            <label><span className="etiqueta">Domicilio</span><input className="campo" {...campo("domicilio")} /></label>
            <label><span className="etiqueta">CP</span><input className="campo" inputMode="numeric" maxLength={5} {...campo("codigo_postal")} /></label>
          </div>
          <label className="mt-3 block"><span className="etiqueta">Régimen fiscal</span><input className="campo" {...campo("regimen_fiscal")} /></label>
        </details>
        <label className="block"><span className="etiqueta">Etiquetas (separadas por coma)</span><input className="campo" placeholder="Ej. Laboral, Iguala, VIP" {...campo("etiquetas")} /></label>
        <label className="block"><span className="etiqueta">Notas internas</span><textarea className="campo" rows={2} {...campo("notas")} /></label>
        <Aviso>{error}</Aviso>
        {duplicado && <Aviso tipo="alerta">{duplicado} <button type="button" className="ml-1 font-semibold underline" onClick={(e) => guardar(e as any, true)}>Es otra persona: guardar de todos modos</button></Aviso>}
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar cliente</button></div>
      </form>
    </Modal>
  );
}

export function LigaCliente({ id, nombre }: { id?: number | null; nombre?: string | null }) {
  if (!id) return null;
  return <Link href={`/clientes/${id}`} className="font-semibold text-turquesa-700 hover:underline">👤 {nombre || "Ver cliente"}</Link>;
}

/** Para abrir el alta de un módulo desde la ficha del cliente: «?nuevo=1&cliente=ID». */
export function useClienteDeUrl(): { nuevo: boolean; cliente: ClienteBreve | null; listo: boolean } {
  const [r, setR] = useState<{ nuevo: boolean; cliente: ClienteBreve | null; listo: boolean }>({ nuevo: false, cliente: null, listo: false });
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const id = Number(p.get("cliente"));
    const nuevo = p.get("nuevo") === "1";
    if (!id) { setR({ nuevo, cliente: null, listo: true }); return; }
    api.get(`/clientes/${id}`).then((c) => setR({ nuevo, listo: true, cliente: { id: c.id, nombre: c.nombre, rfc: c.rfc, email: c.email, telefono: c.telefono, tipo: c.tipo } }))
      .catch(() => setR({ nuevo, cliente: null, listo: true }));
    window.history.replaceState(null, "", window.location.pathname);
  }, []);
  return r;
}
