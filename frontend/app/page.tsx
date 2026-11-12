"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Chip, Modal } from "@/components/ui";
import { api, fecha, mxn } from "@/lib/api";

function quincenasEntre(ini: string, fin: string): number | null {
  if (!ini || !fin) return null;
  const [a1, m1, d1] = ini.split("-").map(Number);
  const [a2, m2, d2] = fin.split("-").map(Number);
  const finMes = new Date(a2, m2, 0).getDate();
  if (![1, 16].includes(d1) || ![15, finMes].includes(d2)) return null;
  const n = (a2 * 12 + m2) * 2 + (d2 === 15 ? 1 : 2) - ((a1 * 12 + m1) * 2 + (d1 === 1 ? 1 : 2)) + 1;
  return n > 0 ? n : null;
}

function NuevoExpediente({ onCerrar, onCreado }: { onCerrar: () => void; onCreado: (id: number) => void }) {
  const [versiones, setVersiones] = useState<any[]>([]);
  const [f, setF] = useState({ trabajador_nombre: "", identificador_laboral: "", periodo_inicio: "", periodo_fin: "", quincenas_esperadas: "", catalogo_version_id: "" });
  const [error, setError] = useState("");
  const [archivos, setArchivos] = useState<File[]>([]);
  const [lectura, setLectura] = useState<any>(null);
  const [estado, setEstado] = useState<"" | "leyendo" | "creando" | "subiendo">("");
  const entrada = useRef<HTMLInputElement>(null);
  useEffect(() => {
    api.get("/catalogos").then((cats: any[]) => {
      const activas = cats.flatMap((c) => c.versiones.filter((v: any) => v.estado === "activo"));
      setVersiones(activas);
      if (activas.length === 1) setF((x) => ({ ...x, catalogo_version_id: String(activas[0].id) }));
    }).catch((e) => setError(e.message));
  }, []);
  const calculadas = quincenasEntre(f.periodo_inicio, f.periodo_fin);
  const cambiar = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  const aplicar = (t: any) => setF((x) => ({
    ...x, trabajador_nombre: t.nombre || x.trabajador_nombre, identificador_laboral: t.identificador_laboral || "",
    periodo_inicio: t.periodo_inicio || x.periodo_inicio, periodo_fin: t.periodo_fin || x.periodo_fin, quincenas_esperadas: "",
  }));

  async function leer(lista: FileList | null) {
    const nuevos = Array.from(lista || []).filter((a) => a.name.toLowerCase().endsWith(".pdf"));
    if (!nuevos.length) return;
    const todos = [...archivos, ...nuevos.filter((n) => !archivos.some((a) => a.name === n.name && a.size === n.size))];
    setError(""); setEstado("leyendo");
    try {
      const fd = new FormData();
      todos.forEach((a) => fd.append("archivos", a));
      const r = await api.subir("/expedientes/prelectura", fd);
      setArchivos(todos); setLectura(r);
      if (r.sugerencia) aplicar(r.sugerencia);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setEstado("");
      if (entrada.current) entrada.current.value = "";
    }
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setEstado("creando");
    let id: number | null = null;
    try {
      const r = await api.post("/expedientes", {
        ...f, identificador_laboral: f.identificador_laboral || null,
        quincenas_esperadas: f.quincenas_esperadas ? Number(f.quincenas_esperadas) : null,
        catalogo_version_id: Number(f.catalogo_version_id),
      });
      id = r.id;
      if (archivos.length) {
        setEstado("subiendo");
        const fd = new FormData();
        archivos.forEach((a) => fd.append("archivos", a));
        await api.subir(`/expedientes/${id}/documentos`, fd);
      }
      onCreado(r.id);
    } catch (err: any) {
      if (id !== null) onCreado(id); // el expediente existe; los archivos pueden subirse desde «Documentos»
      else { setError(err.message); setEstado(""); }
    }
  }
  const s = lectura?.sugerencia;
  const ocupado = estado !== "";
  return (
    <Modal titulo="Nuevo expediente" onCerrar={onCerrar} ancho="max-w-xl">
      <form onSubmit={enviar} className="space-y-3">
        <div className={`rounded-2xl border-2 border-dashed p-4 text-center transition ${estado === "leyendo" ? "border-turquesa bg-turquesa-50" : "border-crema-300 bg-crema/60 hover:border-turquesa"}`}
          onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (!ocupado) leer(e.dataTransfer.files); }}>
          <input ref={entrada} type="file" accept="application/pdf,.pdf" multiple className="hidden" onChange={(e) => leer(e.target.files)} />
          <p className="font-marca text-sm font-bold text-marino">Suba los comprobantes y llenamos los datos por usted</p>
          <p className="mt-0.5 text-xs text-slate-500">Leemos nombre, clave de servidor y periodos de los recibos. Usted revisa y confirma.</p>
          <button type="button" className="btn-turquesa mt-3" disabled={ocupado} onClick={() => entrada.current?.click()}>
            {estado === "leyendo" ? "Leyendo recibos…" : archivos.length ? "Agregar más PDF" : "Elegir PDF de recibos"}
          </button>
          {archivos.length > 0 && (
            <ul className="mt-3 space-y-1 text-left text-xs">
              {archivos.map((a, i) => {
                const info = lectura?.archivos?.find((x: any) => x.nombre === a.name);
                return (
                  <li key={a.name + a.size} className="flex items-center justify-between gap-2 rounded-lg bg-white px-2.5 py-1.5">
                    <span className="truncate"><b>{a.name}</b>{info && <span className="text-slate-500"> · {info.paginas} págs. · {info.recibos} recibos{info.ocr > 0 && ` · ${info.ocr} con OCR`}{info.sin_clasificar > 0 && ` · ${info.sin_clasificar} sin clasificar`}</span>}</span>
                    <button type="button" className="shrink-0 text-red-700 hover:underline" disabled={ocupado} aria-label={`Quitar ${a.name}`}
                      onClick={() => { const resto = archivos.filter((_, j) => j !== i); setArchivos(resto); if (!resto.length) setLectura(null); }}>Quitar</button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        {lectura && (
          <div className="space-y-2">
            {s ? (
              <Aviso tipo="ok">
                Detectamos <b>{s.recibos}</b> recibo(s) de <b>{s.nombre || "trabajador sin nombre legible"}</b>
                {s.periodo_inicio && <>, del <b>{fecha(s.periodo_inicio)}</b> al <b>{fecha(s.periodo_fin)}</b> ({s.quincenas_con_recibo} de {s.quincenas_en_periodo} quincenas)</>}.
                {s.plazas.length > 1 && <> Hay {s.plazas.length} plazas.</>} Revise los datos antes de crear.
              </Aviso>
            ) : <Aviso tipo="alerta">No pudimos proponer datos a partir de estos archivos. Captúrelos a mano.</Aviso>}
            {lectura.avisos.map((a: string, i: number) => <Aviso key={i} tipo="alerta">{a}</Aviso>)}
            {lectura.trabajadores.filter((t: any) => t.identificado).length > 1 && (
              <label className="block"><span className="etiqueta">Trabajador de este expediente</span>
                <select className="campo" onChange={(e) => aplicar(lectura.trabajadores[Number(e.target.value)])}>
                  {lectura.trabajadores.map((t: any, i: number) => t.identificado && <option key={i} value={i}>{t.nombre || t.identificador_laboral} — {t.recibos} recibo(s)</option>)}
                </select></label>
            )}
          </div>
        )}
        <label className="block"><span className="etiqueta">Nombre del trabajador</span>
          <input className="campo" required minLength={2} value={f.trabajador_nombre} onChange={cambiar("trabajador_nombre")} /></label>
        <label className="block"><span className="etiqueta">Identificador laboral (opcional)</span>
          <input className="campo" value={f.identificador_laboral} onChange={cambiar("identificador_laboral")} placeholder="Clave de servidor" />
          <span className="mt-1 block text-xs text-slate-500">Si lo captura, los recibos se asignan por este identificador y no por el nombre.</span></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="etiqueta">Periodo: inicio</span>
            <input className="campo" type="date" required value={f.periodo_inicio} onChange={cambiar("periodo_inicio")} /></label>
          <label className="block"><span className="etiqueta">Periodo: fin</span>
            <input className="campo" type="date" required value={f.periodo_fin} onChange={cambiar("periodo_fin")} /></label>
        </div>
        <p className="text-xs text-slate-500">Debe iniciar el día 1 o 16 y terminar el día 15 o fin de mes.
          {calculadas !== null && <> El periodo contiene <b>{calculadas}</b> quincenas.</>}
          {s?.periodo_inicio && <> Amplíelo si el análisis debe cubrir quincenas de las que aún no tiene recibo.</>}</p>
        <label className="block"><span className="etiqueta">Quincenas esperadas</span>
          <input className="campo" type="number" min={1} max={600} value={f.quincenas_esperadas} onChange={cambiar("quincenas_esperadas")}
            placeholder={calculadas !== null ? `${calculadas} (según el periodo)` : "p. ej. 72"} /></label>
        <label className="block"><span className="etiqueta">Catálogo de prestaciones (versión validada)</span>
          <select className="campo" required value={f.catalogo_version_id} onChange={cambiar("catalogo_version_id")}>
            <option value="">Seleccione…</option>
            {versiones.map((v) => <option key={v.id} value={v.id}>{v.catalogo} — versión {v.numero} ({v.entradas_total} claves)</option>)}
          </select>
          {versiones.length === 0 && <span className="mt-1 block text-xs text-amber-700">No hay catálogos validados. Un administrador debe activar uno en «Catálogos».</span>}</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar} disabled={estado === "creando" || estado === "subiendo"}>Cancelar</button>
          <button className="btn-primario" disabled={ocupado}>
            {estado === "creando" ? "Creando…" : estado === "subiendo" ? "Subiendo comprobantes…" : archivos.length ? `Crear y procesar ${archivos.length} PDF` : "Crear expediente"}</button></div>
      </form>
    </Modal>
  );
}

export default function Expedientes() {
  const sesion = useSesion();
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const cargar = useCallback(() => api.get("/expedientes").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const editor = sesion && sesion.usuario.rol !== "consulta";
  const conPendientes = (lista || []).filter((e) => e.estado !== "validado" && e.resumen.alertas_bloqueantes > 0);
  const tarjetas = [
    { t: "Expedientes", v: lista?.length ?? "—" },
    { t: "Con pendientes de revisión", v: lista ? conPendientes.length : "—", alerta: conPendientes.length > 0 },
    { t: "Listos para validar", v: lista ? lista.filter((e) => e.estado === "pendiente_revision" && e.resumen.alertas_bloqueantes === 0).length : "—" },
    { t: "Validados", v: lista ? lista.filter((e) => e.estado === "validado").length : "—" },
  ];
  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Expedientes</h1><p className="mt-1 text-sm text-slate-500">Sus expedientes y lo que falta por revisar en cada uno.</p></div>
        {editor && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo expediente</button>}
      </div>
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {tarjetas.map((c) => (
          <div key={c.t} className={`tarjeta p-5 ${c.alerta ? "border-amber-300 bg-amber-50" : ""}`}>
            <div className="etiqueta">{c.t}</div>
            <div className="font-marca text-3xl font-extrabold text-marino">{c.v}</div>
          </div>
        ))}
      </div>
      <Aviso>{error}</Aviso>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Expediente</th><th>Trabajador</th><th>Periodo</th><th>Estado</th><th>Pendientes</th><th>Quincenas</th><th className="num">Total autorizado</th></tr></thead>
          <tbody>
            {lista === null && <tr><td colSpan={7} className="text-slate-500">Cargando…</td></tr>}
            {lista?.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-slate-500">Aún no hay expedientes.{editor && " Cree el primero con «Nuevo expediente»."}</td></tr>}
            {lista?.map((e) => (
              <tr key={e.id} className="hover:bg-marino-50/50">
                <td><Link className="font-semibold text-marino underline-offset-2 hover:underline" href={`/expedientes/${e.id}`}>#{e.id}</Link></td>
                <td><Link href={`/expedientes/${e.id}`} className="hover:underline">{e.trabajador_nombre}</Link>
                  <div className="text-xs text-slate-500">{e.catalogo.nombre} · v{e.catalogo.version}</div></td>
                <td className="whitespace-nowrap">{fecha(e.periodo_inicio)} – {fecha(e.periodo_fin)}</td>
                <td><Chip estado={e.estado} /></td>
                <td>{e.estado === "validado" ? <span className="text-slate-400">—</span>
                  : e.resumen.alertas_bloqueantes > 0 ? <span className="font-semibold text-amber-700">{e.resumen.alertas_bloqueantes} por resolver</span>
                  : <span className="text-emerald-700">Sin pendientes</span>}</td>
                <td className="whitespace-nowrap">{e.resumen.quincenas_con_recibo}/{e.resumen.quincenas_esperadas}
                  {e.resumen.quincenas_faltantes > 0 && <span className="ml-1 text-xs text-red-700">({e.resumen.quincenas_faltantes} faltantes)</span>}</td>
                <td className="num">{e.total_expediente === null ? "Por plaza" : mxn(e.total_expediente)}
                  {e.provisional && <div className="font-sans text-xs text-amber-700">provisional</div>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {nuevo && <NuevoExpediente onCerrar={() => setNuevo(false)} onCreado={(id) => (window.location.href = `/expedientes/${id}`)} />}
    </Shell>
  );
}
