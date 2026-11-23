"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { FormCliente } from "@/components/clientes";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { api, hoyLocal, mxn } from "@/lib/api";

const ESTADO_CARGO: Record<string, [string, string]> = {
  pagado: ["Pagado", "bg-emerald-100 text-emerald-800"], parcial: ["Pago parcial", "bg-amber-100 text-amber-800"],
  pendiente: ["Por vencer", "bg-slate-100 text-slate-700"], vencido: ["Vencido", "bg-red-100 text-red-800"], cancelado: ["Cancelado", "bg-slate-100 text-slate-400 line-through"],
};
const NUEVO_EN: Record<string, [string, string]> = {
  agenda: ["Asunto en Agenda", "/agenda/asuntos?nuevo=1&cliente="], evidencia: ["Carpeta en Evidencia", "/evidencia?nuevo=1&cliente="],
  afore: ["Caso en AFORE", "/afore/casos/nuevo?directorio="], nomina: ["Expediente de nómina", "/app?nuevo=1&cliente="],
};
const fechaCorta = (s: string) => new Date(s + "T12:00").toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" });

export default function FichaCliente() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [dialogo, setDialogo] = useState<string>("");
  const [cancelar, setCancelar] = useState<{ tipo: "cargo" | "pago"; id: number; texto: string } | null>(null);
  const cargar = useCallback(() => api.get(`/clientes/${id}`).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function accion(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { const r = await f(); if (r && r.id) setC(r); else cargar(); setOk(msg); } catch (e: any) { setError(e.message); }
  }
  async function subirDoc(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    if (!(d.get("archivo") as File)?.size) return setError("Elija un archivo.");
    await accion(() => api.subir(`/clientes/${id}/documentos`, d), "Documento guardado.");
    e.currentTarget?.reset?.();
    setDialogo("");
  }
  async function abrirDoc(doc: any) {
    try { const { blob } = await api.blob(`/clientes/documentos/${doc.id}/archivo`); window.open(URL.createObjectURL(blob), "_blank", "noopener"); }
    catch (e: any) { setError(e.message); }
  }
  if (!c) return <Shell><Aviso>{error}</Aviso></Shell>;
  const cta = c.cuenta;
  const pendientes = c.cargos.filter((g: any) => ["pendiente", "parcial", "vencido"].includes(g.estado));
  return (
    <Shell>
      <Link href="/clientes" className="text-sm font-semibold text-turquesa-700">← Clientes</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">{c.nombre} {c.estado === "inactivo" && <span className="align-middle text-sm font-semibold text-slate-400">(inactivo)</span>}</h1>
          <p className="mt-1 text-sm text-slate-500">{[c.tipo === "moral" ? "Persona moral" : "Persona física", c.rfc, c.responsable && `Responsable: ${c.responsable}`].filter(Boolean).join(" · ")}</p>
        </div>
        {c.puede_editar && <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => setDialogo("editar")}>Editar datos</button>
          <button className="btn-sec" onClick={() => accion(() => api.put(`/clientes/${id}/estado`, { estado: c.estado === "activo" ? "inactivo" : "activo" }), "Listo.")}>
            {c.estado === "activo" ? "Marcar inactivo" : "Reactivar"}</button>
          {c.es_admin && <button className="btn-sec text-red-700" onClick={() => setDialogo("eliminar")}>Eliminar</button>}</div>}
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-5">
          {/* ---------------- Cobranza ---------------- */}
          <section className="tarjeta overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-4 py-3">
              <h2 className="font-semibold text-marino">Honorarios y pagos</h2>
              {c.puede_editar && <div className="flex flex-wrap gap-2">
                <button className="btn-sec" onClick={() => setDialogo("cargo")}>+ Honorario</button>
                <button className="btn-turquesa" onClick={() => setDialogo("pago")}>Registrar pago</button>
                {Number(cta.saldo) > 0 && <button className="btn-sec" onClick={() => setDialogo("recordatorio")}>Enviar recordatorio</button>}</div>}
            </div>
            <div className="grid grid-cols-2 gap-px bg-crema-200 sm:grid-cols-4">
              {[["Saldo", cta.saldo, ""], ["Vencido", cta.vencido, Number(cta.vencido) ? "text-red-700" : ""], ["Por vencer", cta.por_vencer, ""], ["Pagado", cta.pagado, "text-emerald-700"]].map(([t, v, cl]) =>
                <div key={t} className="bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">{t}</p><p className={`text-lg font-extrabold text-marino ${cl}`}>{mxn(v)}</p></div>)}
            </div>
            {Number(cta.a_favor) > 0 && <p className="bg-emerald-50 px-4 py-2 text-sm text-emerald-800">Saldo a favor del cliente: <b>{mxn(cta.a_favor)}</b></p>}
            {c.cargos.length ? <table className="w-full text-sm"><thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
              <th className="px-4 py-2">Concepto</th><th className="px-4 py-2">Vence</th><th className="px-4 py-2 text-right">Monto</th><th className="px-4 py-2 text-right">Pendiente</th><th className="px-4 py-2">Estado</th><th /></tr></thead>
              <tbody className="divide-y divide-crema-200">{c.cargos.map((g: any) => (
                <tr key={g.id} className={g.estado === "cancelado" ? "text-slate-400" : ""}>
                  <td className="px-4 py-2">{g.concepto}{g.relacionado && <Link href={g.relacionado.ruta} className="block text-xs text-turquesa-700 hover:underline">{g.relacionado.titulo}</Link>}
                    {g.motivo_cancelacion && <p className="text-xs">Cancelado: {g.motivo_cancelacion}</p>}</td>
                  <td className="px-4 py-2 whitespace-nowrap">{fechaCorta(g.vence)}</td>
                  <td className="px-4 py-2 text-right">{mxn(g.monto)}</td>
                  <td className="px-4 py-2 text-right font-semibold">{Number(g.pendiente) ? mxn(g.pendiente) : "—"}</td>
                  <td className="px-4 py-2"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_CARGO[g.estado][1]}`}>{ESTADO_CARGO[g.estado][0]}</span></td>
                  <td className="px-2 py-2 text-right">{c.puede_editar && g.estado !== "cancelado" && g.estado !== "pagado" &&
                    <button className="text-xs text-slate-500 underline" onClick={() => setCancelar({ tipo: "cargo", id: g.id, texto: g.concepto })}>Cancelar</button>}</td>
                </tr>))}</tbody></table>
              : <p className="p-6 text-center text-sm text-slate-500">Sin honorarios registrados. Agregue un pago único, parcialidades o una iguala mensual.</p>}
            {c.pagos.length > 0 && <>
              <h3 className="border-t border-crema-300 bg-crema/40 px-4 py-2 text-xs font-bold uppercase tracking-wide text-slate-500">Pagos recibidos</h3>
              <ul className="divide-y divide-crema-200">{c.pagos.map((p: any) => (
                <li key={p.id} className={`flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm ${p.cancelado ? "text-slate-400 line-through" : ""}`}>
                  <span><b className="text-marino">{mxn(p.monto)}</b> · {fechaCorta(p.fecha)} · {p.metodo_texto}{p.referencia ? ` (${p.referencia})` : ""} · <span className="text-slate-500">{p.concepto}</span>
                    {p.cancelado && <span className="ml-1 no-underline">— cancelado: {p.motivo_cancelacion}</span>}</span>
                  <span className="flex gap-3 text-xs"><span className="text-slate-400">Folio {p.folio}</span>
                    <Link href={`/clientes/recibo/${p.id}`} className="font-semibold text-turquesa-700 underline">Recibo</Link>
                    {c.es_admin && !p.cancelado && <button className="text-slate-500 underline" onClick={() => setCancelar({ tipo: "pago", id: p.id, texto: `pago folio ${p.folio}` })}>Cancelar</button>}</span>
                </li>))}</ul></>}
          </section>

          {/* ---------------- Módulos ---------------- */}
          <section className="tarjeta p-4">
            <h2 className="font-semibold text-marino">Asuntos y expedientes del cliente</h2>
            {c.vinculos.length ? <ul className="mt-2 divide-y divide-crema-200">{c.vinculos.map((v: any) => (
              <li key={`${v.modulo}-${v.id}`} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span><span className="mr-2 rounded-full bg-crema px-2 py-0.5 text-xs font-semibold text-slate-600">{v.etiqueta}</span>
                  <Link href={v.ruta} className="font-semibold text-marino hover:underline">{v.titulo}</Link>
                  {v.detalle && <span className="ml-2 text-xs text-slate-500">{v.detalle}</span>}</span>
                {c.puede_editar && <button className="text-xs text-slate-500 underline" onClick={() => accion(() => api.put("/clientes/vinculos/modulo", { modulo: v.modulo, id: v.id, cliente_id: null }), "Desligado.")}>Desligar</button>}
              </li>))}</ul> : <p className="mt-1 text-sm text-slate-500">Aún no está ligado a ningún módulo.</p>}
            {c.puede_editar && c.estado === "activo" && <div className="mt-3 flex flex-wrap gap-2">{c.modulos.filter((k: string) => NUEVO_EN[k]).map((k: string) =>
              <Link key={k} href={NUEVO_EN[k][1] + c.id} className="btn-sec text-sm">+ {NUEVO_EN[k][0]}</Link>)}</div>}
          </section>
        </div>

        <div className="space-y-5">
          <section className="tarjeta p-4 text-sm">
            <h2 className="mb-2 font-semibold text-marino">Datos</h2>
            <dl className="space-y-1.5">{[["Correo", c.email], ["Teléfono", c.telefono], ["Contacto", c.contacto], ["CURP", c.curp_pista && `${c.curp_pista} (guardada cifrada)`],
              ["Domicilio", [c.domicilio, c.codigo_postal && `CP ${c.codigo_postal}`].filter(Boolean).join(", ")], ["Régimen fiscal", c.regimen_fiscal]].filter(([, v]) => v).map(([k, v]) =>
              <div key={k as string} className="grid grid-cols-[6.5rem_1fr] gap-2"><dt className="text-slate-500">{k}</dt><dd className="break-words text-slate-800">{v}</dd></div>)}</dl>
            {(c.etiquetas || []).length > 0 && <p className="mt-2">{c.etiquetas.map((e: string) => <span key={e} className="mr-1 rounded-full bg-crema px-2 py-0.5 text-xs">{e}</span>)}</p>}
            {c.notas && <p className="mt-3 whitespace-pre-line rounded-lg bg-crema/60 p-2 text-slate-700">{c.notas}</p>}
          </section>
          <section className="tarjeta p-4 text-sm">
            <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-marino">Documentos</h2>
              {c.puede_editar && <button className="text-sm font-semibold text-turquesa-700 underline" onClick={() => setDialogo("documento")}>+ Subir</button>}</div>
            {c.documentos.length ? <ul className="divide-y divide-crema-200">{c.documentos.map((d: any) => (
              <li key={d.id} className="flex items-center justify-between gap-2 py-2">
                <button className="text-left" onClick={() => abrirDoc(d)}><span className="font-semibold text-marino hover:underline">{d.nombre}</span>
                  <span className="block text-xs text-slate-500">{d.tipo_texto} · {(d.tamano / 1024).toFixed(0)} KB</span></button>
                {c.puede_editar && <button className="text-xs text-slate-500 underline" onClick={() => accion(() => api.borrar(`/clientes/documentos/${d.id}`), "Documento eliminado.")}>Quitar</button>}
              </li>))}</ul> : <p className="text-slate-500">INE, constancia fiscal, comprobante de domicilio, contrato de servicios, poderes…</p>}
          </section>
        </div>
      </div>

      {dialogo === "editar" && <FormCliente cliente={c} onCerrar={() => setDialogo("")} onGuardado={(r) => { setC(r); setDialogo(""); setOk("Datos guardados."); }} />}
      {dialogo === "cargo" && <FormCargo c={c} onCerrar={() => setDialogo("")} onListo={(r) => { setC(r); setDialogo(""); setOk("Honorario registrado."); }} />}
      {dialogo === "pago" && <FormPago c={c} pendientes={pendientes} onCerrar={() => setDialogo("")} onListo={(r) => { setC(r); setDialogo(""); setOk("Pago registrado."); router.push(`/clientes/recibo/${r.pago_id}`); }} />}
      {dialogo === "recordatorio" && <Recordatorio c={c} onCerrar={() => setDialogo("")} onListo={(m) => { setDialogo(""); setOk(m); }} />}
      {dialogo === "documento" && <Modal titulo="Subir documento del cliente" onCerrar={() => setDialogo("")}>
        <form className="space-y-3" onSubmit={subirDoc}>
          <label className="block"><span className="etiqueta">Tipo</span><select className="campo" name="tipo">{Object.entries(c.tipos_documento).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
          <label className="block"><span className="etiqueta">Nombre (opcional)</span><input className="campo" name="nombre" placeholder="Ej. INE vigente" /></label>
          <label className="block"><span className="etiqueta">Archivo (PDF, JPG, PNG o WebP, hasta 15 MB)</span><input className="campo" type="file" name="archivo" accept="application/pdf,image/jpeg,image/png,image/webp" required /></label>
          <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={() => setDialogo("")}>Cancelar</button><button className="btn-turquesa">Subir</button></div>
        </form></Modal>}
      {dialogo === "eliminar" && <ConfirmarEliminar titulo={`Eliminar a ${c.nombre}`} onCerrar={() => setDialogo("")}
        onConfirmar={async () => { try { await api.borrar(`/clientes/${id}`); router.push("/clientes"); } catch (e: any) { setDialogo(""); setError(e.message); } }}>
        Se borran sus datos y documentos. Si tiene pagos o asuntos ligados no se podrá borrar: márquelo como inactivo.</ConfirmarEliminar>}
      {cancelar && <Cancelar titulo={`Cancelar ${cancelar.texto}`} onCerrar={() => setCancelar(null)} onConfirmar={(motivo) => {
        const ruta = cancelar.tipo === "cargo" ? `/clientes/cargos/${cancelar.id}/cancelar` : `/clientes/pagos/${cancelar.id}/cancelar`;
        setCancelar(null); accion(() => api.post(ruta, { motivo }), "Cancelado. Queda el registro con el motivo.");
      }} />}
    </Shell>
  );
}

function FormCargo({ c, onCerrar, onListo }: { c: any; onCerrar: () => void; onListo: (r: any) => void }) {
  const [f, setF] = useState({ concepto: "", monto: "", vence: hoyLocal(), modo: "unico", meses: "6", relacionado: "" });
  const [error, setError] = useState("");
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    const [modulo, rid] = f.relacionado.split(":");
    try {
      onListo(await api.post(`/clientes/${c.id}/cargos`, { concepto: f.concepto, monto: f.monto, vence: f.vence,
        repetir_meses: f.modo === "unico" ? 1 : Number(f.meses), relacionado: modulo ? { modulo, id: Number(rid) } : null }));
    } catch (e: any) { setError(e.message); }
  }
  return (
    <Modal titulo="Nuevo honorario" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={guardar}>
        <div className="flex flex-wrap gap-4 text-sm">{[["unico", "Pago único"], ["mensual", "Iguala o mensualidades"]].map(([v, t]) =>
          <label key={v} className="flex items-center gap-2"><input type="radio" checked={f.modo === v} onChange={() => setF({ ...f, modo: v })} /> {t}</label>)}</div>
        <label className="block"><span className="etiqueta">Concepto</span><input className="campo" required minLength={2} placeholder={f.modo === "unico" ? "Ej. Honorarios por demanda laboral" : "Ej. Iguala mensual"} value={f.concepto} onChange={(e) => setF({ ...f, concepto: e.target.value })} /></label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label><span className="etiqueta">{f.modo === "unico" ? "Monto" : "Monto por mes"}</span><input className="campo" required inputMode="decimal" placeholder="0.00" value={f.monto} onChange={(e) => setF({ ...f, monto: e.target.value.replace(/[^\d.]/g, "") })} /></label>
          <label><span className="etiqueta">{f.modo === "unico" ? "Vence" : "Primer vencimiento"}</span><input className="campo" type="date" required value={f.vence} onChange={(e) => setF({ ...f, vence: e.target.value })} /></label>
          {f.modo === "mensual" && <label><span className="etiqueta">Número de meses</span><input className="campo" type="number" min={2} max={36} value={f.meses} onChange={(e) => setF({ ...f, meses: e.target.value })} /></label>}
        </div>
        {c.vinculos.length > 0 && <label className="block"><span className="etiqueta">Asunto (opcional)</span>
          <select className="campo" value={f.relacionado} onChange={(e) => setF({ ...f, relacionado: e.target.value })}><option value="">Sin asunto específico</option>
            {c.vinculos.filter((v: any) => v.modulo !== "leads").map((v: any) => <option key={`${v.modulo}:${v.id}`} value={`${v.modulo}:${v.id}`}>{v.etiqueta}: {v.titulo}</option>)}</select></label>}
        {f.modo === "mensual" && Number(f.monto) > 0 && <p className="text-sm text-slate-600">Se crearán {f.meses} cargos de {mxn(Number(f.monto).toFixed(2))}, uno por mes.</p>}
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function FormPago({ c, pendientes, onCerrar, onListo }: { c: any; pendientes: any[]; onCerrar: () => void; onListo: (r: any) => void }) {
  const [f, setF] = useState({ monto: pendientes[0]?.pendiente || "", fecha: hoyLocal(), metodo: "transferencia", referencia: "", nota: "", cargo_id: "" });
  const [error, setError] = useState("");
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { onListo(await api.post(`/clientes/${c.id}/pagos`, { ...f, cargo_id: f.cargo_id ? Number(f.cargo_id) : null, referencia: f.referencia || null, nota: f.nota || null })); }
    catch (e: any) { setError(e.message); }
  }
  return (
    <Modal titulo="Registrar pago recibido" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={guardar}>
        <p className="text-sm text-slate-600">Registre aquí el dinero que ya recibió (transferencia, efectivo, terminal…). Nomira no cobra a su cliente.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Monto recibido</span><input className="campo" required inputMode="decimal" value={f.monto} onChange={(e) => setF({ ...f, monto: e.target.value.replace(/[^\d.]/g, "") })} /></label>
          <label><span className="etiqueta">Fecha</span><input className="campo" type="date" required max={hoyLocal()} value={f.fecha} onChange={(e) => setF({ ...f, fecha: e.target.value })} /></label>
          <label><span className="etiqueta">Forma de pago</span><select className="campo" value={f.metodo} onChange={(e) => setF({ ...f, metodo: e.target.value })}>
            {Object.entries(c.metodos).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
          <label><span className="etiqueta">Referencia (opcional)</span><input className="campo" placeholder="Ej. folio SPEI" value={f.referencia} onChange={(e) => setF({ ...f, referencia: e.target.value })} /></label>
        </div>
        <label className="block"><span className="etiqueta">Aplicar a</span><select className="campo" value={f.cargo_id} onChange={(e) => {
          const g = pendientes.find((x) => String(x.id) === e.target.value); setF({ ...f, cargo_id: e.target.value, monto: g ? g.pendiente : f.monto }); }}>
          <option value="">A cuenta (se aplica a lo más antiguo)</option>
          {pendientes.map((g) => <option key={g.id} value={g.id}>{g.concepto} — pendiente {mxn(g.pendiente)}</option>)}</select></label>
        <label className="block"><span className="etiqueta">Nota (opcional)</span><input className="campo" value={f.nota} onChange={(e) => setF({ ...f, nota: e.target.value })} /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Registrar y ver recibo</button></div>
      </form>
    </Modal>
  );
}

function Recordatorio({ c, onCerrar, onListo }: { c: any; onCerrar: () => void; onListo: (m: string) => void }) {
  const [mensaje, setMensaje] = useState("");
  const [vista, setVista] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.post(`/clientes/${c.id}/recordatorio`, { mensaje }).then(setVista).catch((e) => setError(e.message)); }, [c.id]); // eslint-disable-line react-hooks/exhaustive-deps
  async function enviar() {
    setError("");
    try { const r = await api.post(`/clientes/${c.id}/recordatorio`, { mensaje, enviar: true }); onListo(`Recordatorio enviado a ${r.para}.`); } catch (e: any) { setError(e.message); }
  }
  return (
    <Modal titulo="Recordatorio de pago" onCerrar={onCerrar} ancho="max-w-xl">
      <div className="space-y-3 text-sm">
        <p>Para: <b>{c.email || "— el cliente no tiene correo registrado —"}</b></p>
        <label className="block"><span className="etiqueta">Mensaje personal (opcional)</span><textarea className="campo" rows={2} value={mensaje} onChange={(e) => setMensaje(e.target.value)} placeholder="Ej. Le recordamos que puede pagar por transferencia a la cuenta de siempre." /></label>
        {vista && <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-xl bg-crema/60 p-3 font-sans text-xs text-slate-700">{vista.texto}</pre>}
        <Aviso>{error}</Aviso>
        {vista && !vista.puede_enviar && <Aviso tipo="alerta">{c.email ? "El envío de correos aún no está configurado en Nomira." : "Agregue el correo del cliente para poder enviarlo."} Puede copiar el texto y mandarlo por WhatsApp.</Aviso>}
        <div className="flex justify-end gap-2"><button className="btn-sec" onClick={() => { navigator.clipboard?.writeText(vista?.texto || ""); }}>Copiar texto</button>
          <button className="btn-turquesa" disabled={!vista?.puede_enviar} onClick={enviar}>Enviar por correo</button></div>
      </div>
    </Modal>
  );
}

function Cancelar({ titulo, onCerrar, onConfirmar }: { titulo: string; onCerrar: () => void; onConfirmar: (motivo: string) => void }) {
  const [motivo, setMotivo] = useState("");
  return (
    <Modal titulo={titulo} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onConfirmar(motivo); }}>
        <p className="text-sm text-slate-600">No se borra: queda en el historial como cancelado, con el motivo.</p>
        <label className="block"><span className="etiqueta">Motivo</span><input className="campo" required minLength={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Volver</button><button className="btn-turquesa">Cancelar registro</button></div>
      </form>
    </Modal>
  );
}
