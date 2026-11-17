"use client";
import { useCallback, useEffect, useState } from "react";
import ShellPlataforma, { Credenciales } from "@/components/plataforma";
import { Aviso, Chip, Modal } from "@/components/ui";
import { fechaHora } from "@/lib/api";
import { apiP, avisarContadores } from "@/lib/plataforma";

export default function Solicitudes() {
  const [lista, setLista] = useState<any[] | null>(null);
  const [filtro, setFiltro] = useState<"nueva" | "atendida" | "todas">("nueva");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [nota, setNota] = useState<any>(null);
  const [convertir, setConvertir] = useState<any>(null);
  const [acceso, setAcceso] = useState<any>(null);
  const cargar = useCallback(() => apiP.get("/solicitudes").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const cambiar = async (s: any, estado: string, textoNota: string | null) => {
    setError(""); setOk("");
    try { await apiP.patch(`/solicitudes/${s.id}`, { estado, nota: textoNota }); avisarContadores(); await cargar(); }
    catch (e: any) { setError(e.message); }
  };
  const visibles = (lista || []).filter((s) => filtro === "todas" || s.estado === filtro);
  const cuenta = (e: string) => (lista || []).filter((s) => s.estado === e).length;
  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Solicitudes</h1>
      <p className="mb-5 mt-1 text-sm text-slate-500">Personas que pidieron informes o una suscripción desde la página de inicio.</p>
      <div className="mb-4 flex flex-wrap gap-2" role="tablist">
        {([["nueva", `Por atender (${cuenta("nueva")})`], ["atendida", `Atendidas (${cuenta("atendida")})`], ["todas", "Todas"]] as const).map(([v, t]) => (
          <button key={v} role="tab" aria-selected={filtro === v} onClick={() => setFiltro(v)}
            className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${filtro === v ? "bg-marino text-white" : "bg-white text-slate-600 ring-1 ring-crema-300 hover:bg-crema"}`}>{t}</button>
        ))}
      </div>
      <div className="mb-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="space-y-3">
        {lista === null && <p className="text-sm text-slate-500">Cargando…</p>}
        {lista && visibles.length === 0 && <div className="tarjeta p-8 text-center text-sm text-slate-500">{filtro === "nueva" ? "No hay solicitudes por atender." : "No hay solicitudes."}</div>}
        {visibles.map((s) => (
          <article key={s.id} className={`tarjeta p-5 ${s.estado === "nueva" ? "ring-1 ring-amber-200" : ""}`}>
            <div className="flex flex-wrap items-start gap-3">
              <div className="min-w-[14rem] flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${s.tipo === "suscripcion" ? "bg-turquesa-100 text-turquesa-700" : "bg-marino-50 text-marino"}`}>{s.tipo === "suscripcion" ? "Quiere suscribirse" : "Pide informes"}</span>
                  <Chip estado={s.estado === "atendida" ? "activo" : "pendiente"} texto={s.estado === "atendida" ? "Atendida" : "Nueva"} />
                  <span className="text-xs text-slate-500">{fechaHora(s.creado_en)}</span>
                </div>
                <h2 className="mt-2 text-lg font-bold text-marino">{s.nombre}{s.empresa && <span className="font-medium text-slate-500"> · {s.empresa}</span>}</h2>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <a className="font-semibold text-turquesa-700 hover:underline" href={`mailto:${s.email}`}>{s.email}</a>
                  {s.telefono && <a className="text-slate-600 hover:underline" href={`tel:${s.telefono}`}>{s.telefono}</a>}
                  {s.expedientes_mes && <span className="text-slate-500">{s.expedientes_mes} expedientes/mes</span>}
                </div>
                {s.mensaje && <p className="mt-3 whitespace-pre-wrap rounded-xl bg-crema p-3 text-sm text-slate-700">{s.mensaje}</p>}
                {s.nota && <p className="mt-2 whitespace-pre-wrap text-xs italic text-slate-500">Nota interna: {s.nota}</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-turquesa" onClick={() => setConvertir(s)}>Convertir en cliente</button>
                <button className="btn-sec" onClick={() => setNota(s)}>Nota</button>
                {s.estado === "nueva"
                  ? <button className="btn-sec" onClick={() => cambiar(s, "atendida", s.nota)}>Marcar atendida</button>
                  : <button className="btn-sec" onClick={() => cambiar(s, "nueva", s.nota)}>Reabrir</button>}
              </div>
            </div>
          </article>
        ))}
      </div>
      {nota && <NotaModal s={nota} onCerrar={() => setNota(null)} onGuardar={async (t) => { await cambiar(nota, nota.estado, t || null); setNota(null); }} />}
      {convertir && <ConvertirModal s={convertir} onCerrar={() => setConvertir(null)}
        onListo={(r) => { setConvertir(null); setAcceso(r.acceso); setOk(`${r.cliente.nombre} ya es cliente de Nomira.`); avisarContadores(); cargar(); }} />}
      {acceso && <Credenciales acceso={acceso} titulo="Cliente creado: datos de acceso" onCerrar={() => setAcceso(null)} />}
    </ShellPlataforma>
  );
}

function NotaModal({ s, onCerrar, onGuardar }: { s: any; onCerrar: () => void; onGuardar: (t: string) => Promise<void> }) {
  const [t, setT] = useState(s.nota || "");
  return (
    <Modal titulo={`Nota sobre ${s.nombre}`} onCerrar={onCerrar}>
      <textarea className="campo h-32" maxLength={2000} value={t} onChange={(e) => setT(e.target.value)} placeholder="Ej. Se le llamó el martes; enviar cotización." autoFocus />
      <p className="mt-1 text-xs text-slate-500">Solo la ven los administradores de la plataforma.</p>
      <div className="mt-3 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
        <button className="btn-primario" onClick={() => onGuardar(t)}>Guardar nota</button></div>
    </Modal>
  );
}

function ConvertirModal({ s, onCerrar, onListo }: { s: any; onCerrar: () => void; onListo: (r: any) => void }) {
  const [f, setF] = useState({ organizacion: s.empresa || "", admin_nombre: s.nombre, admin_email: s.email });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { onListo(await apiP.post(`/solicitudes/${s.id}/convertir`, f)); } catch (err: any) { setError(err.message); setEnviando(false); }
  }
  return (
    <Modal titulo="Convertir en cliente" onCerrar={onCerrar} ancho="max-w-xl">
      <form className="space-y-4" onSubmit={enviar}>
        <p className="text-sm text-slate-600">Se crea la cuenta de la empresa y su primer <b>administrador</b> con una contraseña temporal. La solicitud queda como atendida.</p>
        <label className="block"><span className="etiqueta">Nombre de la empresa (cliente)</span>
          <input className="campo" required minLength={2} value={f.organizacion} onChange={(e) => setF({ ...f, organizacion: e.target.value })} autoFocus /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">Administrador del cliente</span>
            <input className="campo" required minLength={2} value={f.admin_nombre} onChange={(e) => setF({ ...f, admin_nombre: e.target.value })} /></label>
          <label className="block"><span className="etiqueta">Su correo</span>
            <input className="campo" type="email" required value={f.admin_email} onChange={(e) => setF({ ...f, admin_email: e.target.value })} /></label>
        </div>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando}>{enviando ? "Creando…" : "Crear cliente"}</button></div>
      </form>
    </Modal>
  );
}
