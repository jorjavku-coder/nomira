"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Chip } from "@/components/ui";
import { api, fecha } from "@/lib/api";

export default function Catalogos() {
  const sesion = useSesion();
  const admin = sesion?.usuario.rol === "administrador";
  const [cats, setCats] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState("");
  const [nombre, setNombre] = useState("");
  const archivos = useRef<Record<number, HTMLInputElement | null>>({});
  const cargar = useCallback(() => api.get("/catalogos").then(setCats).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);

  async function accion(texto: string, fn: () => Promise<any>) {
    setError(""); setOcupado(texto);
    try { return await fn(); } catch (e: any) { setError(e.message); } finally { setOcupado(""); cargar(); }
  }
  return (
    <Shell>
      <h1 className="mb-1 text-3xl font-extrabold text-marino">Catálogos de prestaciones</h1>
      <p className="mb-4 max-w-3xl text-sm text-slate-600">
        Solo se suman las percepciones cuya clave coincide exactamente con una clave activa del catálogo. Cada cambio crea una
        versión nueva: los expedientes conservan la versión con la que se calcularon.
      </p>
      <Aviso>{error}</Aviso>
      {ocupado && <Aviso tipo="info">{ocupado}</Aviso>}
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
                    if (v?.id) window.location.href = `/catalogos/${v.id}`;
                  }} />
                <button className="btn-turquesa" disabled={!!ocupado} onClick={() => archivos.current[c.id]?.click()}>Leer catálogo desde PDF (OCR)</button>
                <button className="btn-sec" disabled={!!ocupado} onClick={async () => {
                  const activa = c.versiones.find((v: any) => v.estado === "activo");
                  const v = await accion("Creando versión…", () => api.post(`/catalogos/${c.id}/versiones`, { copiar_de_version_id: activa?.id ?? null }));
                  if (v?.id) window.location.href = `/catalogos/${v.id}`;
                }}>{c.versiones.some((v: any) => v.estado === "activo") ? "Nueva versión (copia de la activa)" : "Nueva versión vacía"}</button>
              </div>
            )}
          </div>
          <table className="tabla">
            <thead><tr><th>Versión</th><th>Estado</th><th>Origen</th><th>Claves</th><th>Por revisar</th><th>Creada</th><th>Validada</th></tr></thead>
            <tbody>
              {c.versiones.length === 0 && <tr><td colSpan={7} className="text-slate-500">Sin versiones.</td></tr>}
              {[...c.versiones].reverse().map((v: any) => (
                <tr key={v.id}>
                  <td><Link className="font-semibold text-marino hover:underline" href={`/catalogos/${v.id}`}>Versión {v.numero}</Link></td>
                  <td><Chip estado={v.estado} /></td>
                  <td>{{ ocr: "OCR de PDF", manual: "Manual", copia: "Copia" }[v.origen as string]}{v.archivo_nombre ? ` · ${v.archivo_nombre}` : ""}</td>
                  <td>{v.entradas_total}</td>
                  <td>{v.por_revisar > 0 ? <span className="font-semibold text-amber-700">{v.por_revisar}</span> : "0"}</td>
                  <td>{fecha(v.creado_en)}</td><td>{fecha(v.validado_en)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </Shell>
  );
}
