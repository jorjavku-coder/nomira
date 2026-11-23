"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { FormCliente } from "@/components/clientes";
import { Aviso, Modal } from "@/components/ui";
import { api, mxn } from "@/lib/api";

const FILTROS: [string, string][] = [["", "Activos"], ["con_saldo", "Con saldo"], ["vencidos", "Con pagos vencidos"], ["inactivos", "Inactivos"]];

export default function Clientes() {
  const router = useRouter();
  const [r, setR] = useState<any>(null);
  const [q, setQ] = useState("");
  const [filtro, setFiltro] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [dialogo, setDialogo] = useState<"" | "nuevo" | "importar" | "unir">("");
  const cargar = useCallback(() => {
    const p = new URLSearchParams({ estado: filtro === "inactivos" ? "inactivo" : "activo" });
    if (q.trim()) p.set("q", q.trim());
    if (filtro && filtro !== "inactivos") p.set("filtro", filtro);
    api.get(`/clientes?${p}`).then(setR).catch((e) => setError(e.message));
  }, [q, filtro]);
  useEffect(() => { const t = setTimeout(cargar, 200); return () => clearTimeout(t); }, [cargar]);
  const t = r?.totales;
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Mi despacho</p>
          <h1 className="text-3xl font-extrabold text-marino">Clientes y cobranza</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Capture a cada cliente una sola vez: sus datos, documentos y pagos quedan aquí, y en cada módulo solo lo elige.</p></div>
        <div className="flex flex-wrap items-center gap-2"><BotonAyuda modulo="clientes" />
          {r?.puede_editar && <><button className="btn-sec" onClick={() => setDialogo("importar")}>Importar de Excel</button>
            <button className="btn-turquesa" onClick={() => setDialogo("nuevo")}>+ Nuevo cliente</button></>}</div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {r?.sugerencias > 0 && <button onClick={() => setDialogo("unir")} className="mb-4 flex w-full items-center justify-between gap-3 rounded-2xl border-2 border-turquesa bg-turquesa-50 p-4 text-left text-marino">
        <span><b>Encontramos {r.sugerencias} cliente(s) que ya capturó en los módulos</b> y todavía no están en este directorio. Únalos con un clic para no escribirlos otra vez.</span>
        <span className="whitespace-nowrap font-semibold text-turquesa-700">Revisar →</span></button>}
      {t && <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Tarjeta titulo="Por cobrar" valor={mxn(t.por_cobrar)} nota="Saldo pendiente de todos sus clientes" />
        <Tarjeta titulo="Vencido" valor={mxn(t.vencido)} nota="Pagos que ya pasaron su fecha" alerta={Number(t.vencido) > 0} onClick={() => setFiltro("vencidos")} />
        <Tarjeta titulo="Cobrado este mes" valor={mxn(t.cobrado_mes)} nota="Pagos registrados desde el día 1" />
      </div>}
      <div className="tarjeta overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-crema-300 p-3">
          <input className="campo max-w-sm" placeholder="Buscar por nombre, RFC, correo o teléfono" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar clientes" />
          <div className="flex flex-wrap gap-1">{FILTROS.map(([v, txt]) => <button key={v} onClick={() => setFiltro(v)}
            className={`rounded-full px-3 py-1.5 text-sm font-semibold ${filtro === v ? "bg-marino text-white" : "bg-crema text-slate-600 hover:bg-crema-200"}`}>{txt}</button>)}</div>
        </div>
        {r && (r.clientes.length ? <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
            <th className="px-4 py-2">Cliente</th><th className="px-4 py-2">Contacto</th><th className="px-4 py-2 text-right">Saldo</th>
            <th className="px-4 py-2 text-right">Vencido</th><th className="px-4 py-2">Próximo pago</th></tr></thead>
          <tbody className="divide-y divide-crema-200">{r.clientes.map((c: any) => (
            <tr key={c.id} className="cursor-pointer hover:bg-crema/50" onClick={() => router.push(`/clientes/${c.id}`)}>
              <td className="px-4 py-3"><Link href={`/clientes/${c.id}`} className="font-semibold text-marino hover:underline">{c.nombre}</Link>
                <p className="text-xs text-slate-500">{[c.tipo === "moral" ? "Persona moral" : "Persona física", c.rfc].filter(Boolean).join(" · ")}
                  {(c.etiquetas || []).map((e: string) => <span key={e} className="ml-1 rounded-full bg-crema px-2 py-0.5 text-[11px]">{e}</span>)}</p></td>
              <td className="px-4 py-3 text-slate-600">{c.email || "—"}<p className="text-xs">{c.telefono}</p></td>
              <td className="px-4 py-3 text-right font-semibold text-marino">{Number(c.cuenta.saldo) ? mxn(c.cuenta.saldo) : "—"}</td>
              <td className={`px-4 py-3 text-right font-semibold ${Number(c.cuenta.vencido) ? "text-red-700" : "text-slate-400"}`}>{Number(c.cuenta.vencido) ? mxn(c.cuenta.vencido) : "—"}</td>
              <td className="px-4 py-3 text-slate-600">{c.cuenta.proximo_vencimiento ? new Date(c.cuenta.proximo_vencimiento + "T12:00").toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" }) : "—"}</td>
            </tr>))}</tbody></table></div>
          : <div className="p-10 text-center">
            <p className="font-semibold text-marino">{q || filtro ? "No hay clientes con ese filtro." : "Aún no tiene clientes en su directorio."}</p>
            {!q && !filtro && r.puede_editar && <p className="mt-1 text-sm text-slate-500">Empiece con <button className="font-semibold text-turquesa-700 underline" onClick={() => setDialogo("nuevo")}>un cliente nuevo</button> (puede subir su constancia fiscal) o <button className="font-semibold text-turquesa-700 underline" onClick={() => setDialogo("importar")}>importe su lista de Excel</button>.</p>}
          </div>)}
      </div>
      {dialogo === "nuevo" && <FormCliente onCerrar={() => setDialogo("")} onGuardado={(c) => router.push(`/clientes/${c.id}`)} />}
      {dialogo === "importar" && <Importar onCerrar={() => setDialogo("")} onListo={(n) => { setDialogo(""); setOk(`Se dieron de alta ${n} cliente(s).`); cargar(); }} />}
      {dialogo === "unir" && <Unir onCerrar={() => { setDialogo(""); cargar(); }} />}
    </Shell>
  );
}

function Tarjeta({ titulo, valor, nota, alerta, onClick }: { titulo: string; valor: string; nota: string; alerta?: boolean; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick} className={`tarjeta p-4 text-left ${alerta ? "border-red-200 bg-red-50" : ""}`}>
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{titulo}</p>
      <p className={`mt-1 text-2xl font-extrabold ${alerta ? "text-red-700" : "text-marino"}`}>{valor}</p>
      <p className="text-xs text-slate-500">{nota}</p>
    </button>
  );
}

function Importar({ onCerrar, onListo }: { onCerrar: () => void; onListo: (n: number) => void }) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [vista, setVista] = useState<any>(null);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  async function enviar(confirmar: boolean, a = archivo) {
    if (!a) return;
    setError("");
    const d = new FormData(); d.append("archivo", a); d.append("confirmar", String(confirmar));
    try { const r = await api.subir("/clientes/importar", d); if (confirmar) onListo(r.nuevos); else setVista(r); } catch (e: any) { setError(e.message); }
  }
  const ESTADO: Record<string, string> = { nuevo: "text-emerald-700", repetido: "text-slate-500", error: "text-red-700" };
  return (
    <Modal titulo="Importar clientes de Excel" onCerrar={onCerrar} ancho="max-w-2xl">
      <div className="space-y-3 text-sm">
        <p className="text-slate-600">Suba su lista en Excel (.xlsx) o CSV. Debe tener al menos la columna <b>Nombre</b>; también leemos RFC, CURP, correo, teléfono, domicilio, CP y notas.
          {" "}<button className="font-semibold text-turquesa-700 underline" onClick={() => api.descargar("/clientes/importar/plantilla", "plantilla-clientes-nomira.xlsx")}>Descargar plantilla</button></p>
        <input ref={input} className="campo" type="file" accept=".xlsx,.csv" onChange={(e) => { const a = e.target.files?.[0] || null; setArchivo(a); setVista(null); if (a) enviar(false, a); }} />
        <Aviso>{error}</Aviso>
        {vista && <>
          <p><b className="text-emerald-700">{vista.nuevos} nuevos</b> · {vista.repetidos} ya estaban · <span className={vista.errores ? "text-red-700" : ""}>{vista.errores} con errores</span></p>
          <div className="max-h-64 overflow-auto rounded-xl border border-crema-300"><table className="w-full text-xs"><tbody className="divide-y divide-crema-200">
            {vista.filas.map((f: any) => <tr key={f.fila}><td className="px-2 py-1 text-slate-400">Fila {f.fila}</td><td className="px-2 py-1 font-semibold">{f.nombre}</td>
              <td className={`px-2 py-1 ${ESTADO[f.estado]}`}>{f.estado === "nuevo" ? "Se dará de alta" : f.motivo}</td></tr>)}</tbody></table></div>
        </>}
        <div className="flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={!vista?.nuevos} onClick={() => enviar(true)}>Dar de alta {vista?.nuevos || ""} cliente(s)</button></div>
      </div>
    </Modal>
  );
}

function Unir({ onCerrar }: { onCerrar: () => void }) {
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const cargar = () => api.get("/clientes/sugerencias/modulos").then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  async function unir(g: any) {
    setError("");
    try { await api.post("/clientes/sugerencias/unir", { nombre: g.nombre, items: g.items, cliente_id: g.cliente_existente?.id || null, ...g.datos }); cargar(); }
    catch (e: any) { setError(e.message); }
  }
  return (
    <Modal titulo="Clientes que ya capturó en los módulos" onCerrar={onCerrar} ancho="max-w-2xl">
      <p className="mb-3 text-sm text-slate-600">Agrupamos los nombres iguales que aparecen en sus módulos. Al unirlos se crea (o se usa) el cliente del directorio y queda ligado a cada asunto o expediente.</p>
      <Aviso>{error}</Aviso>
      {lista && !lista.length && <Aviso tipo="ok">¡Listo! Todo lo de sus módulos ya está ligado al directorio.</Aviso>}
      <ul className="max-h-[60vh] divide-y divide-crema-200 overflow-auto">{lista?.map((g) => (
        <li key={g.clave} className="flex items-start justify-between gap-3 py-3 text-sm">
          <div><p className="font-semibold text-marino">{g.nombre}</p>
            <p className="text-xs text-slate-500">{g.items.map((i: any) => `${i.etiqueta}: ${i.titulo}`).join(" · ")}</p>
            {g.cliente_existente && <p className="text-xs text-turquesa-700">Ya existe en Clientes: se ligará a «{g.cliente_existente.nombre}»</p>}</div>
          <button className="btn-sec whitespace-nowrap" onClick={() => unir(g)}>{g.cliente_existente ? "Ligar" : "Crear y ligar"}</button>
        </li>))}</ul>
      <div className="mt-3 flex justify-end"><button className="btn-turquesa" onClick={onCerrar}>Terminar</button></div>
    </Modal>
  );
}
