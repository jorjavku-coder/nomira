"use client";
import { useCallback, useEffect, useState } from "react";
import { ComercialShell } from "@/components/comercial";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { fecha, mxn } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

const COLOR: Record<string, string> = {
  activo: "bg-emerald-100 text-emerald-800", suspendido: "bg-slate-200 text-slate-700", programado: "bg-sky-100 text-sky-800",
  vencido: "bg-amber-100 text-amber-800", agotado: "bg-amber-100 text-amber-800",
};
const VACIO = { codigo: "", descripcion: "", tipo: "porcentaje", valor: "", aplica_a: "todo", inicia_en: "", vence_en: "", usos_maximos: "", minimo: "" };

function FormCupon({ inicial, soloPct, maximo, onCerrar, onListo }: { inicial: any; soloPct: boolean; maximo: string; onCerrar: () => void; onListo: () => void }) {
  const [f, setF] = useState<any>(inicial ? { ...VACIO, ...Object.fromEntries(Object.entries(inicial).map(([k, v]) => [k, v ?? ""])) } : VACIO);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  async function guardar(ev: React.FormEvent) {
    ev.preventDefault();
    setError(""); setOcupado(true);
    const cuerpo = { codigo: f.codigo, descripcion: f.descripcion || null, tipo: f.tipo, valor: f.valor, aplica_a: f.aplica_a,
      inicia_en: f.inicia_en || null, vence_en: f.vence_en || null, usos_maximos: f.usos_maximos ? Number(f.usos_maximos) : null, minimo: f.minimo || null };
    try {
      if (inicial) await apiP.put(`/comercial/cupones/${inicial.id}`, cuerpo); else await apiP.post("/comercial/cupones", cuerpo);
      onListo();
    } catch (e: any) { setError(e.message); setOcupado(false); }
  }
  return (
    <Modal titulo={inicial ? `Editar ${inicial.codigo}` : "Nuevo cupón"} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-3">
        <label className="block"><span className="etiqueta">Código</span>
          <input className="campo font-mono uppercase" required minLength={3} maxLength={40} placeholder="BLACKDAY2026" value={f.codigo}
            onChange={(e) => setF({ ...f, codigo: e.target.value.replace(/\s/g, "").toUpperCase() })} />
          <span className="mt-0.5 block text-xs text-slate-500">Letras y números, sin espacios ni acentos (se permiten - y _). Es lo que escribe el cliente.</span></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Tipo</span><select className="campo" value={f.tipo} onChange={set("tipo")} disabled={soloPct}>
            <option value="porcentaje">Porcentaje</option><option value="monto">Monto fijo (MXN)</option></select></label>
          <label><span className="etiqueta">{f.tipo === "porcentaje" ? "Porcentaje de descuento" : "Monto de descuento (MXN)"}</span>
            <input className="campo" required inputMode="decimal" value={f.valor} onChange={set("valor")} placeholder={f.tipo === "porcentaje" ? "20" : "500"} />
            {soloPct && <span className="mt-0.5 block text-xs text-slate-500">Su máximo autorizado: {Number(maximo)} %.</span>}</label>
          <label><span className="etiqueta">Se aplica a</span><select className="campo" value={f.aplica_a} onChange={set("aplica_a")}>
            <option value="todo">Todo el subtotal</option><option value="recurrente">Solo la suscripción (no servicios ni cursos)</option></select></label>
          <label><span className="etiqueta">Compra mínima antes de IVA (opcional)</span><input className="campo" inputMode="decimal" value={f.minimo} onChange={set("minimo")} /></label>
          <label><span className="etiqueta">Válido desde (opcional)</span><input className="campo" type="date" value={f.inicia_en} onChange={set("inicia_en")} /></label>
          <label><span className="etiqueta">Válido hasta (opcional)</span><input className="campo" type="date" value={f.vence_en} onChange={set("vence_en")} /></label>
          <label><span className="etiqueta">Límite de usos (opcional)</span><input className="campo" inputMode="numeric" value={f.usos_maximos} onChange={set("usos_maximos")} placeholder="Sin límite" /></label>
        </div>
        <label className="block"><span className="etiqueta">Descripción interna (opcional)</span><textarea className="campo" rows={2} maxLength={300} value={f.descripcion} onChange={set("descripcion")} placeholder="Campaña, motivo, quién lo autorizó" /></label>
        <p className="text-xs text-slate-500">El descuento se calcula sobre el subtotal antes de IVA. Un uso cuenta cuando la cotización queda pagada.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={ocupado}>{ocupado ? "Guardando…" : "Guardar cupón"}</button></div>
      </form>
    </Modal>
  );
}

export default function Cupones() {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [form, setForm] = useState<any>(null);
  const [borrar, setBorrar] = useState<any>(null);
  const cargar = useCallback(() => apiP.get("/comercial/cupones").then(setR).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  async function estado(c: any, e: string) {
    setError(""); setOk("");
    try { await apiP.post(`/comercial/cupones/${c.id}/estado`, { estado: e }); setOk(`${c.codigo} ${e === "activo" ? "activado" : "suspendido"}.`); cargar(); }
    catch (x: any) { setError(x.message); }
  }
  return (
    <ComercialShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Cupones de descuento</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Códigos como BLACKDAY2026 que se aplican al preparar una cotización o que el cliente captura en su propuesta antes de aceptarla.</p></div>
        {r?.puede_gestionar && <button className="btn-turquesa" onClick={() => setForm("nuevo")}>+ Nuevo cupón</button>}
      </div>
      <div className="mb-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {r && (r.cupones.length ? (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-crema-300 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="p-3">Código</th><th className="p-3">Descuento</th><th className="p-3">Vigencia</th><th className="p-3">Usos</th><th className="p-3">Estado</th><th className="p-3" /></tr></thead>
            <tbody>{r.cupones.map((c: any) => (
              <tr key={c.id} className="border-b border-crema-200 last:border-0">
                <td className="p-3"><span className="font-mono font-bold text-marino">{c.codigo}</span>{c.descripcion && <p className="text-xs text-slate-500">{c.descripcion}</p>}</td>
                <td className="p-3">{c.tipo === "porcentaje" ? `${Number(c.valor)} %` : mxn(c.valor)}
                  <p className="text-xs text-slate-500">{c.aplica_a === "recurrente" ? "Solo suscripción" : "Todo el subtotal"}{c.minimo ? ` · mínimo ${mxn(c.minimo)}` : ""}</p></td>
                <td className="p-3 text-xs text-slate-600">{c.inicia_en || c.vence_en ? <>{c.inicia_en ? fecha(c.inicia_en) : "Ya"} → {c.vence_en ? fecha(c.vence_en) : "sin fin"}</> : "Sin fecha límite"}</td>
                <td className="p-3">{c.usos}{c.usos_maximos ? ` / ${c.usos_maximos}` : ""}</td>
                <td className="p-3"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${COLOR[c.vigencia]}`}>{c.vigencia_texto}</span></td>
                <td className="p-3 text-right">{r.puede_gestionar && <div className="flex flex-wrap justify-end gap-2 text-xs font-semibold">
                  {c.estado === "activo" ? <button className="text-amber-700 underline" onClick={() => estado(c, "suspendido")}>Suspender</button>
                    : <button className="text-emerald-700 underline" onClick={() => estado(c, "activo")}>Activar</button>}
                  <button className="text-turquesa-700 underline" onClick={() => setForm(c)}>Editar</button>
                  {!c.usos && <button className="text-red-700 underline" onClick={() => setBorrar(c)}>Borrar</button>}</div>}</td>
              </tr>))}</tbody>
          </table>
        </div>
      ) : <div className="tarjeta p-10 text-center"><p className="font-semibold text-marino">Aún no hay cupones.</p>
        {r.puede_gestionar && <p className="mt-1 text-sm text-slate-500">Cree el primero con «+ Nuevo cupón».</p>}</div>)}
      {form && <FormCupon inicial={form === "nuevo" ? null : form} soloPct={r.solo_porcentaje} maximo={r.maximo_pct}
        onCerrar={() => setForm(null)} onListo={() => { setForm(null); setOk("Cupón guardado."); cargar(); }} />}
      {borrar && <ConfirmarEliminar titulo={`Borrar ${borrar.codigo}`} onCerrar={() => setBorrar(null)}
        onConfirmar={async () => { await apiP.borrar(`/comercial/cupones/${borrar.id}`); setOk("Cupón borrado."); cargar(); }}>
        El cupón aún no se ha usado en ningún pago. Si prefiere conservarlo, suspéndalo.</ConfirmarEliminar>}
    </ComercialShell>
  );
}
