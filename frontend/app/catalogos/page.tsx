"use client";
import Link from "next/link";
import BotonAyuda from "@/components/BotonAyuda";
import { useCallback, useEffect, useRef, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Chip, ConfirmarEliminar, Modal } from "@/components/ui";
import { api, fecha } from "@/lib/api";

export default function Catalogos() {
  const sesion = useSesion();
  const admin = sesion?.usuario.rol === "administrador";
  const [cats, setCats] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState("");
  const [nombre, setNombre] = useState("");
  const [borrar, setBorrar] = useState<{ tipo: "catalogo" | "version"; c: any; v?: any } | null>(null);
  const [ok, setOk] = useState("");
  const [enUso, setEnUso] = useState<{ c: any; lista: any[] } | null>(null);
  const archivos = useRef<Record<number, HTMLInputElement | null>>({});
  const cargar = useCallback(() => api.get("/catalogos").then(setCats).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);

  async function accion(texto: string, fn: () => Promise<any>) {
    setError(""); setOcupado(texto);
    try { return await fn(); } catch (e: any) { setError(e.message); } finally { setOcupado(""); cargar(); }
  }
  return (
    <Shell>
      <div className="mb-1 flex flex-wrap items-center gap-3"><h1 className="text-3xl font-extrabold text-marino">Catálogos de prestaciones</h1><BotonAyuda modulo="nomina" /></div>
      <p className="mb-4 max-w-3xl text-sm text-slate-600">
        Solo se suman las percepciones cuya clave coincide exactamente con una clave activa del catálogo. Si a un catálogo le faltan
        claves, use «Agregar claves faltantes»: se crea una versión nueva y, al activarla, puede aplicarla a los expedientes en revisión.
      </p>
      <Aviso>{error}</Aviso>
      {ocupado && <Aviso tipo="info">{ocupado}</Aviso>}
      <Aviso tipo="ok">{ok}</Aviso>
      {admin && (
        <form className="tarjeta my-4 flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); accion("Creando…", () => api.post("/catalogos", { nombre })).then(() => setNombre("")); }}>
          <label className="block grow"><span className="etiqueta">Nuevo catálogo</span>
            <input className="campo" required minLength={2} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre, p. ej. Prestaciones 2025" /></label>
          <button className="btn-primario">Crear catálogo</button>
        </form>
      )}
      {cats?.length === 0 && <div className="tarjeta p-8 text-center text-slate-500">No hay catálogos todavía.</div>}
      {cats?.map((c) => (
        <section key={c.id} className="tarjeta mb-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-4 py-3">
            <h2 className="font-semibold text-marino">{c.nombre}</h2>
            {admin && (
              <div className="flex flex-wrap gap-2">
                <input type="file" accept="application/pdf,.pdf" className="hidden" ref={(el) => { archivos.current[c.id] = el; }}
                  onChange={async (e) => {
                    const a = e.target.files?.[0];
                    if (!a) return;
                    const fd = new FormData(); fd.append("archivo", a);
                    const v = await accion("Leyendo el PDF con OCR… puede tardar unos segundos.", () => api.subir(`/catalogos/${c.id}/versiones/ocr`, fd));
                    e.target.value = "";
                    if (v?.id) window.location.href = `/catalogos/${v.id}?paso=1`;
                  }} />
                <button className="btn-turquesa" disabled={!!ocupado} onClick={() => archivos.current[c.id]?.click()}>Leer catálogo desde PDF (OCR)</button>
                <button className="btn-peligro" disabled={!!ocupado} onClick={async () => {
                  if (c.expedientes > 0) setEnUso({ c, lista: await api.get(`/catalogos/${c.id}/expedientes`).catch(() => []) });
                  else setBorrar({ tipo: "catalogo", c });
                }}>Eliminar catálogo</button>
                {(() => {
                  const borrador = [...c.versiones].reverse().find((v: any) => v.estado === "borrador");
                  const activa = c.versiones.find((v: any) => v.estado === "activo");
                  if (borrador) return <Link className="btn-sec" href={`/catalogos/${borrador.id}`}>Continuar borrador (versión {borrador.numero})</Link>;
                  return (
                    <button className="btn-sec" disabled={!!ocupado} onClick={async () => {
                      const v = await accion("Creando versión…", () => api.post(`/catalogos/${c.id}/versiones`, activa
                        ? { copiar_de_version_id: activa.id, notas: `Copia de la versión ${activa.numero} para agregar claves faltantes` } : {}));
                      if (v?.id) window.location.href = `/catalogos/${v.id}?paso=2`;
                    }}>{activa ? "Agregar claves faltantes" : "Capturar claves a mano"}</button>
                  );
                })()}
              </div>
            )}
          </div>
          <table className="tabla">
            <thead><tr><th>Versión</th><th>Estado</th><th>Origen</th><th>Claves</th><th>Por revisar</th><th>Creada</th><th>Validada</th><th>Expedientes</th>{admin && <th><span className="sr-only">Acciones</span></th>}</tr></thead>
            <tbody>
              {c.versiones.length === 0 && <tr><td colSpan={9} className="text-slate-500">Sin versiones.</td></tr>}
              {[...c.versiones].reverse().map((v: any) => (
                <tr key={v.id}>
                  <td><Link className="font-semibold text-marino hover:underline" href={`/catalogos/${v.id}`}>Versión {v.numero}</Link></td>
                  <td><Chip estado={v.estado} /></td>
                  <td>{{ ocr: "OCR de PDF", manual: "Manual", copia: "Copia" }[v.origen as string]}{v.archivo_nombre ? ` · ${v.archivo_nombre}` : ""}</td>
                  <td>{v.entradas_total}{v.agregadas_manual > 0 && <span className="text-xs text-turquesa-700"> ({v.agregadas_manual} a mano)</span>}</td>
                  <td>{v.por_revisar > 0 ? <span className="font-semibold text-amber-700">{v.por_revisar}</span> : "0"}</td>
                  <td>{fecha(v.creado_en)}</td><td>{fecha(v.validado_en)}</td><td>{v.expedientes || "—"}</td>
                  {admin && <td className="text-right">{v.expedientes > 0 ? <span className="text-xs text-slate-400" title="Una versión que usan expedientes no se puede eliminar">En uso</span>
                    : <button className="text-xs font-semibold text-red-700 hover:underline" onClick={() => setBorrar({ tipo: "version", c, v })}>Eliminar</button>}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {enUso && <Modal titulo={`No se puede eliminar «${enUso.c.nombre}» todavía`} onCerrar={() => setEnUso(null)}>
        <p className="text-sm text-slate-700">Lo usan <b>{enUso.c.expedientes} expediente(s)</b>. Cada expediente guarda con qué catálogo se calculó; si se borrara, perdería esa referencia.</p>
        <p className="mt-2 text-sm text-slate-700">Para eliminarlo, primero elimine estos expedientes o cámbielos a otro catálogo:</p>
        <ul className="mt-3 max-h-60 divide-y divide-crema-200 overflow-auto rounded-xl border border-crema-300 text-sm">{enUso.lista.map((e) => (
          <li key={e.id} className="flex items-center justify-between gap-2 px-3 py-2"><span>{e.nombre} <span className="text-xs text-slate-500">· {String(e.estado).replace(/_/g, " ")}</span></span>
            <Link className="font-semibold text-turquesa-700 hover:underline" href={`/expedientes/${e.id}`}>Abrir</Link></li>))}</ul>
        <div className="mt-4 flex justify-end"><button className="btn-primario" onClick={() => setEnUso(null)}>Entendido</button></div>
      </Modal>}
      {borrar && <ConfirmarEliminar titulo={borrar.tipo === "catalogo" ? `Eliminar «${borrar.c.nombre}»` : `Eliminar la versión ${borrar.v.numero} de «${borrar.c.nombre}»`}
        onCerrar={() => setBorrar(null)}
        onConfirmar={async () => {
          setOk("");
          if (borrar.tipo === "catalogo") await api.borrar(`/catalogos/${borrar.c.id}`); else await api.borrar(`/catalogos/versiones/${borrar.v.id}`);
          setOk(borrar.tipo === "catalogo" ? `Se eliminó el catálogo «${borrar.c.nombre}».` : `Se eliminó la versión ${borrar.v.numero}.`);
          cargar();
        }}>
        {borrar.tipo === "catalogo"
          ? <p>Se eliminarán el catálogo y sus {borrar.c.versiones.length} versión(es) con todas sus claves. Esta acción no se puede deshacer.</p>
          : <p>Se eliminará esta versión con sus {borrar.v.entradas_total} clave(s). Esta acción no se puede deshacer.</p>}
        <p className="mt-2 text-xs text-slate-500">Solo se pueden eliminar catálogos y versiones que no usa ningún expediente.</p>
      </ConfirmarEliminar>}
    </Shell>
  );
}
