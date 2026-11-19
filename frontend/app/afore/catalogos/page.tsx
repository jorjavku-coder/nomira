"use client";
import { useCallback, useEffect, useState } from "react";
import { AforeShell, recargarCatalogos } from "@/components/afore";
import { useSesion } from "@/components/Shell";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

export default function CatalogosAfore() {
  const sesion = useSesion();
  const admin = sesion?.usuario.rol === "administrador";
  const [cfg, setCfg] = useState<any>(null);
  const [tipos, setTipos] = useState<any>({});
  const [tipo, setTipo] = useState("inconformidad_saldo");
  const [texto, setTexto] = useState("");
  const [extra, setExtra] = useState("");
  const [reglas, setReglas] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const cargar = useCallback(async () => {
    try {
      const [c, cat] = await Promise.all([api.get("/afore/config"), api.get("/afore/catalogos")]);
      setCfg(c); setTipos(cat.tipos); setExtra((c.tipos_extra || []).join("\n")); setReglas(c.reglas_plazo || []);
    } catch (e: any) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (cfg) setTexto((cfg.checklists[tipo] || []).join("\n")); }, [cfg, tipo]);
  async function guardar(datos: any, mensaje: string) {
    setError(""); setOk("");
    try { setCfg(await api.patch("/afore/config", datos)); recargarCatalogos(); setOk(mensaje); await cargar(); } catch (e: any) { setError(e.message); }
  }
  if (!cfg) return <AforeShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AforeShell>;
  return (
    <AforeShell>
      <h1 className="text-3xl font-extrabold text-marino">Catálogos y plantillas</h1>
      {!admin && <div className="mt-3"><Aviso tipo="info">Solo un administrador puede modificar los catálogos y las plantillas.</Aviso></div>}
      <div className="mt-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <section className="tarjeta space-y-3 p-5">
          <h2 className="font-semibold text-marino">Checklist por tipo de problema</h2>
          <p className="text-sm text-slate-500">Lista inicial que se copia a cada caso nuevo (y que después se puede editar por caso). Es organización interna, no una lista legal definitiva.</p>
          <select className="campo" value={tipo} onChange={(e) => setTipo(e.target.value)}>{Object.entries(tipos).map(([k, t]: any) => <option key={k} value={k}>{t}{cfg.checklists_propios.includes(k) ? " (personalizado)" : ""}</option>)}</select>
          <textarea className="campo font-mono text-sm" rows={10} disabled={!admin} value={texto} onChange={(e) => setTexto(e.target.value)} aria-label="Un documento por renglón" />
          <p className="text-xs text-slate-500">Un documento o dato por renglón.</p>
          {admin && <div className="flex gap-2"><button className="btn-primario" onClick={() => guardar({ checklists: { [tipo]: texto.split("\n") } }, "Checklist guardado.")}>Guardar</button>
            {cfg.checklists_propios.includes(tipo) && <button className="btn-sec" onClick={() => guardar({ checklists: { [tipo]: [] } }, "Se restauró la lista original.")}>Restaurar original</button>}</div>}
        </section>
        <section className="tarjeta space-y-3 p-5">
          <h2 className="font-semibold text-marino">Tipos de problema propios del despacho</h2>
          <p className="text-sm text-slate-500">Se agregan a la lista del alta de casos. Uno por renglón.</p>
          <textarea className="campo" rows={4} disabled={!admin} value={extra} onChange={(e) => setExtra(e.target.value)} />
          {admin && <button className="btn-primario" onClick={() => guardar({ tipos_extra: extra.split("\n") }, "Tipos guardados.")}>Guardar</button>}
          <h2 className="pt-3 font-semibold text-marino">Reglas para sugerir fechas</h2>
          <p className="text-sm text-slate-500">Solo sugieren una fecha <b>estimada</b> en el seguimiento; nunca crean plazos legales. Indique su fuente y cuándo la revisó.</p>
          {reglas.map((r, i) => (
            <div key={i} className="grid gap-2 rounded-xl border border-crema-300 p-2 sm:grid-cols-[1fr_5rem_1fr_8rem_auto]">
              <input className="campo" disabled={!admin} placeholder="Nombre" value={r.nombre} onChange={(e) => setReglas(reglas.map((x, j) => j === i ? { ...x, nombre: e.target.value } : x))} />
              <input className="campo" disabled={!admin} type="number" min={1} placeholder="Días" value={r.dias} onChange={(e) => setReglas(reglas.map((x, j) => j === i ? { ...x, dias: e.target.value } : x))} />
              <input className="campo" disabled={!admin} placeholder="Fuente" value={r.fuente || ""} onChange={(e) => setReglas(reglas.map((x, j) => j === i ? { ...x, fuente: e.target.value } : x))} />
              <input className="campo" disabled={!admin} type="date" title="Fecha de revisión" value={r.revisado_en || ""} onChange={(e) => setReglas(reglas.map((x, j) => j === i ? { ...x, revisado_en: e.target.value } : x))} />
              {admin && <button className="btn-peligro" aria-label="Quitar regla" onClick={() => setReglas(reglas.filter((_, j) => j !== i))}>✕</button>}
            </div>))}
          {admin && <div className="flex gap-2"><button className="btn-sec" onClick={() => setReglas([...reglas, { nombre: "", dias: 30, fuente: "", revisado_en: "" }])}>+ Regla</button>
            <button className="btn-primario" onClick={() => guardar({ reglas_plazo: reglas }, "Reglas guardadas.")}>Guardar reglas</button></div>}
        </section>
      </div>
      <section className="mt-5 space-y-3">
        <h2 className="font-semibold text-marino">Plantillas de mensajes</h2>
        <p className="text-sm text-slate-500">Mensajes breves: solo pueden usar <code>{"{nombre}"}</code> y <code>{"{enlace}"}</code> (enlace seguro al portal, con vencimiento). No se permiten CURP, NSS, montos ni datos familiares. Para WhatsApp, registre el nombre de la plantilla <b>aprobada por Meta</b> con los mismos parámetros ({"{{1}}"} = nombre, {"{{2}}"} = enlace).</p>
        <div className="grid gap-4 lg:grid-cols-2">{cfg.plantillas.map((p: any) => <Plantilla key={p.clave} p={p} admin={admin} onGuardado={(m: string) => { setOk(m); cargar(); }} onError={setError} />)}</div>
      </section>
    </AforeShell>
  );
}

function Plantilla({ p, admin, onGuardado, onError }: any) {
  const [f, setF] = useState({ texto: p.texto, wa_nombre: p.wa_nombre || "", wa_idioma: p.wa_idioma, wa_aprobada: p.wa_aprobada, envio: p.envio });
  return (
    <div className="tarjeta space-y-2 p-4 text-sm">
      <h3 className="font-semibold text-marino">{p.nombre}</h3>
      <textarea className="campo" rows={3} maxLength={1000} disabled={!admin} value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} />
      <div className="grid gap-2 sm:grid-cols-[1fr_6rem]">
        <input className="campo" disabled={!admin} placeholder="Nombre de la plantilla aprobada en Meta" value={f.wa_nombre} onChange={(e) => setF({ ...f, wa_nombre: e.target.value })} />
        <input className="campo" disabled={!admin} value={f.wa_idioma} onChange={(e) => setF({ ...f, wa_idioma: e.target.value })} aria-label="Idioma" />
      </div>
      <label className="flex items-center gap-2"><input type="checkbox" disabled={!admin} checked={f.wa_aprobada} onChange={(e) => setF({ ...f, wa_aprobada: e.target.checked })} /> Meta ya aprobó esta plantilla</label>
      <label className="flex items-center gap-2">Envío:
        <select className="campo w-auto py-1" disabled={!admin} value={f.envio} onChange={(e) => setF({ ...f, envio: e.target.value })}>
          <option value="aprobacion">Requiere aprobación del abogado (recomendado)</option><option value="automatico">Automático si todo está listo</option></select></label>
      {admin && <button className="btn-primario" onClick={async () => { try { await api.patch(`/afore/plantillas/${p.clave}`, { ...f, wa_nombre: f.wa_nombre || null }); onGuardado("Plantilla guardada."); } catch (e: any) { onError(e.message); } }}>Guardar</button>}
    </div>
  );
}
