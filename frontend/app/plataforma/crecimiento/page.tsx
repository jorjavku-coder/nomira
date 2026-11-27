"use client";
import { useCallback, useEffect, useState } from "react";
import ShellPlataforma from "@/components/plataforma";
import { Aviso, Modal } from "@/components/ui";
import { apiP } from "@/lib/plataforma";

const TIPOS: Record<string, string> = { puntos: "Puntos", descuento: "% de descuento", meses: "Meses gratis" };
const Num = ({ v, set, ...p }: { v: number | null; set: (n: number | null) => void } & any) => (
  <input className="campo" inputMode="numeric" value={v ?? ""} onChange={(e) => set(e.target.value === "" ? null : Number(e.target.value.replace(/\D/g, "")))} {...p} />);

/** Juegos y referidos: reglas, ruleta (con su probabilidad real), tienda de puntos, trivia y red de despachos que reciben casos. */
export default function CrecimientoPanel() {
  const [d, setD] = useState<any>(null);
  const [tab, setTab] = useState<"reglas" | "ruleta" | "tienda" | "trivia" | "red">("reglas");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cfg, setCfg] = useState<any>(null);
  const [premio, setPremio] = useState<any>(null);
  const [pregunta, setPregunta] = useState<any>(null);
  const cargar = useCallback(() => apiP.get("/crecimiento").then((x) => { setD(x); setCfg(x.config); }).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const hecho = (t: string) => { setOk(t); setError(""); setTimeout(() => setOk(""), 3000); cargar(); };
  const guardarCfg = async () => { try { await apiP.put("/crecimiento/config", cfg); hecho("Reglas guardadas."); } catch (e: any) { setError(e.message); } };
  const ed = d?.puede_editar;
  return (
    <ShellPlataforma>
      <div className="mb-5"><h1 className="text-2xl font-extrabold text-marino">Juegos y referidos</h1>
        <p className="text-sm text-slate-500">Trivia, ruleta y tienda de puntos; invitaciones entre despachos; y casos de la calculadora que se reparten por turnos a la red. Aquí solo hay conteos: nunca los datos de las personas.</p></div>
      <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
      {d && <div className="mb-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {[["Usuarios que juegan", d.cifras.jugadores], ["Respuestas de trivia", d.cifras.respuestas], ["Giros de ruleta", d.cifras.giros],
          ["Descuentos entregados", d.cifras.descuentos], ["Meses regalados (juegos)", d.cifras.meses_juegos], ["Despachos invitados", d.cifras.referidos],
          ["Invitados que pagaron", d.cifras.referidos_pagaron], ["Meses regalados (invitaciones)", d.cifras.meses_referidos], ["Casos de la calculadora", d.cifras.casos],
          ["Despachos en la red", d.cifras.despachos_red]].map(([t, n]) => (
          <div key={t as string} className="tarjeta p-4"><p className="text-2xl font-extrabold text-marino">{n as number}</p><p className="text-xs text-slate-500">{t} {t !== "Despachos en la red" && `· ${d.dias} días`}</p></div>))}
      </div>}
      <div className="mb-4 flex rounded-xl bg-crema p-1 text-sm w-fit">{([["reglas", "Reglas"], ["ruleta", "Ruleta"], ["tienda", "Tienda"], ["trivia", "Trivia"], ["red", "Red y referidos"]] as const).map(([v, t]) => (
        <button key={v} onClick={() => setTab(v)} className={`rounded-lg px-3 py-2 font-semibold ${tab === v ? "bg-white text-marino shadow-sm" : "text-slate-500"}`}>{t}</button>))}</div>

      {cfg && tab === "reglas" && <div className="tarjeta max-w-3xl space-y-5 p-6">
        {!ed && <Aviso tipo="info">Solo un superadministrador cambia estas reglas.</Aviso>}
        <fieldset disabled={!ed} className="space-y-5">
          <div><p className="font-bold text-marino">Juegos</p>
            <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={cfg.juegos_activos} onChange={(e) => setCfg({ ...cfg, juegos_activos: e.target.checked })} /> Trivia y tienda de puntos activas</label>
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              <label><span className="etiqueta">Puntos por acierto</span><Num v={cfg.puntos_por_acierto} set={(n: any) => setCfg({ ...cfg, puntos_por_acierto: n ?? 0 })} /></label>
              <label><span className="etiqueta">Preguntas por día</span><Num v={cfg.preguntas_por_dia} set={(n: any) => setCfg({ ...cfg, preguntas_por_dia: n ?? 1 })} /></label>
              <label><span className="etiqueta">Tope de puntos al día por despacho</span><Num v={cfg.tope_puntos_dia_org} set={(n: any) => setCfg({ ...cfg, tope_puntos_dia_org: n ?? 0 })} /></label>
              <label><span className="etiqueta">Meses de regalo por juegos al año</span><Num v={cfg.tope_meses_anual} set={(n: any) => setCfg({ ...cfg, tope_meses_anual: n ?? 0 })} /></label>
            </div></div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="font-bold text-amber-900">Ruleta semanal</p>
            <p className="mt-1 text-sm text-amber-900">Una ruleta con premios es un sorteo. En México, los sorteos pueden requerir permiso de la Dirección General de Juegos y Sorteos (Segob). Enciéndala después de confirmarlo con su abogado.</p>
            <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={cfg.ruleta_activa} onChange={(e) => setCfg({ ...cfg, ruleta_activa: e.target.checked })} /> Ruleta activa</label>
            <label className="mt-2 block max-w-sm"><span className="etiqueta">Número de permiso (se muestra a los despachos)</span><input className="campo" value={cfg.ruleta_permiso || ""} onChange={(e) => setCfg({ ...cfg, ruleta_permiso: e.target.value })} /></label></div>
          <div><p className="font-bold text-marino">Invitaciones entre despachos</p>
            <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={cfg.referidos_activos} onChange={(e) => setCfg({ ...cfg, referidos_activos: e.target.checked })} /> Invitaciones activas</label>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label><span className="etiqueta">Meses gratis para cada uno cuando el invitado paga</span><Num v={cfg.meses_referido} set={(n: any) => setCfg({ ...cfg, meses_referido: n ?? 0 })} /></label>
              <label><span className="etiqueta">Tope de meses por invitar, por despacho al año</span><Num v={cfg.tope_referidos_anual} set={(n: any) => setCfg({ ...cfg, tope_referidos_anual: n ?? 0 })} /></label>
            </div></div>
          <div><p className="font-bold text-marino">Casos de la calculadora</p>
            <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={cfg.casos_activos} onChange={(e) => setCfg({ ...cfg, casos_activos: e.target.checked })} /> Mostrar «Quiero contactar a un abogado» en la calculadora pública</label></div>
          {ed && <button className="btn-turquesa" onClick={guardarCfg}>Guardar reglas</button>}
        </fieldset>
      </div>}

      {d && tab === "ruleta" && <Premios lista={d.ruleta} lugar="ruleta" ed={ed} prob={d.probabilidades} onEditar={setPremio} />}
      {d && tab === "tienda" && <Premios lista={d.tienda} lugar="tienda" ed={ed} onEditar={setPremio} />}

      {d && tab === "trivia" && <div>
        {ed && <button className="btn-turquesa mb-3" onClick={() => setPregunta({ materia: "Laboral", texto: "", opciones: ["", "", "", ""], correcta: 0, explicacion: "", activa: true })}>+ Pregunta</button>}
        <div className="tarjeta overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b border-crema-300 text-left text-xs text-slate-500"><th className="p-3">Pregunta</th><th className="p-3">Materia</th><th className="p-3 text-right">Respuestas</th><th className="p-3 text-right">Aciertos</th><th className="p-3">Estado</th><th /></tr></thead>
          <tbody>{d.preguntas.map((p: any) => (
            <tr key={p.id} className="border-b border-crema-200 last:border-0"><td className="p-3"><span className="text-marino">{p.texto}</span><span className="block text-xs text-emerald-700">✓ {p.opciones[p.correcta]}</span></td>
              <td className="p-3 text-slate-600">{p.materia}</td><td className="p-3 text-right tabular-nums">{p.respuestas}</td>
              <td className="p-3 text-right tabular-nums">{p.respuestas ? `${Math.round((100 * p.aciertos) / p.respuestas)}%` : "—"}</td>
              <td className="p-3">{p.activa ? <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Activa</span> : <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">Apagada</span>}</td>
              <td className="p-3 text-right">{ed && <button className="text-xs font-semibold text-turquesa-700" onClick={() => setPregunta(p)}>Editar</button>}</td></tr>))}</tbody></table></div></div>}

      {d && tab === "red" && <div className="grid gap-5 lg:grid-cols-2">
        <div className="tarjeta p-5"><p className="font-bold text-marino">Despachos que reciben casos</p>
          {d.red.length ? <ul className="mt-2 divide-y divide-crema-200 text-sm">{d.red.map((r: any, k: number) => (
            <li key={k} className="py-2"><div className="flex justify-between gap-3"><b className="text-marino">{r.despacho}</b><span className="tabular-nums">{r.recibidos} casos</span></div>
              <p className="text-xs text-slate-500">{r.estados.join(", ")}{r.tope_mensual ? ` · máx. ${r.tope_mensual} al mes` : ""}{!r.activo ? " · en pausa" : !r.cumple ? " · sin plan pagado o sin Prospectos (no recibe)" : ""}</p></li>))}</ul>
            : <p className="mt-2 text-sm text-slate-500">Ningún despacho se ha sumado. Lo activan en «Gana con Nomira».</p>}
          {!!d.casos_por_estado.length && <><p className="mt-4 font-bold text-marino">Casos por estado</p>
            <ul className="mt-1 text-sm">{d.casos_por_estado.map((x: any) => <li key={x.estado} className="flex justify-between"><span>{x.estado}</span><span className="tabular-nums">{x.casos}</span></li>)}</ul></>}</div>
        <div className="tarjeta p-5"><p className="font-bold text-marino">Invitaciones</p>
          {d.referidos.length ? <ul className="mt-2 divide-y divide-crema-200 text-sm">{d.referidos.map((r: any, k: number) => (
            <li key={k} className="flex justify-between gap-3 py-2"><span><b className="text-marino">{r.invita}</b> invitó a <b className="text-marino">{r.invitado}</b><span className="block text-xs text-slate-500">{r.desde}</span></span>
              <span className={`h-fit rounded-full px-2 py-0.5 text-xs font-semibold ${r.estado === "premiado" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{r.estado === "premiado" ? "Pagó" : "En prueba"}</span></li>))}</ul>
            : <p className="mt-2 text-sm text-slate-500">Aún no hay invitaciones.</p>}</div>
      </div>}

      {premio && <EditorPremio p={premio} onCerrar={() => setPremio(null)} onGuardado={() => { setPremio(null); hecho("Premio guardado."); }} />}
      {pregunta && <EditorPregunta p={pregunta} onCerrar={() => setPregunta(null)} onGuardado={() => { setPregunta(null); hecho("Pregunta guardada."); }} />}
    </ShellPlataforma>
  );
}

function Premios({ lista, lugar, ed, prob, onEditar }: { lista: any[]; lugar: string; ed: boolean; prob?: any[]; onEditar: (p: any) => void }) {
  const pr = (id: number) => prob?.find((x) => x.id === id)?.probabilidad;
  return (<div>
    {ed && <button className="btn-turquesa mb-3" onClick={() => onEditar({ lugar, etiqueta: "", tipo: lugar === "tienda" ? "descuento" : "puntos", valor: 10, peso: lugar === "ruleta" ? 100 : 0, costo: lugar === "tienda" ? 500 : 0, tope_mensual: null, orden: 0, activo: true })}>+ {lugar === "ruleta" ? "Casilla" : "Artículo"}</button>}
    <div className="tarjeta overflow-x-auto"><table className="w-full text-sm">
      <thead><tr className="border-b border-crema-300 text-left text-xs text-slate-500"><th className="p-3">Premio</th><th className="p-3">Tipo</th>
        {lugar === "ruleta" ? <><th className="p-3 text-right">Peso</th><th className="p-3 text-right">Probabilidad</th><th className="p-3 text-right">Tope al mes</th></> : <th className="p-3 text-right">Costo en puntos</th>}<th className="p-3">Estado</th><th /></tr></thead>
      <tbody>{lista.map((p) => (
        <tr key={p.id} className="border-b border-crema-200 last:border-0"><td className="p-3 font-semibold text-marino">{p.etiqueta}</td><td className="p-3 text-slate-600">{TIPOS[p.tipo]}</td>
          {lugar === "ruleta" ? <><td className="p-3 text-right tabular-nums">{p.peso}</td><td className="p-3 text-right tabular-nums">{p.activo && pr(p.id) != null ? `${pr(p.id)}%` : "—"}</td><td className="p-3 text-right tabular-nums">{p.tope_mensual ?? "Sin tope"}</td></>
            : <td className="p-3 text-right tabular-nums">{p.costo.toLocaleString("es-MX")}</td>}
          <td className="p-3">{p.activo ? "Activo" : "Apagado"}</td><td className="p-3 text-right">{ed && <button className="text-xs font-semibold text-turquesa-700" onClick={() => onEditar(p)}>Editar</button>}</td></tr>))}</tbody></table></div>
    {lugar === "ruleta" && <p className="mt-2 text-xs text-slate-500">La probabilidad es el peso de cada casilla entre la suma de los pesos activos. Los despachos ven esta tabla junto a la ruleta. Si una casilla llega a su tope del mes, deja de salir.</p>}
  </div>);
}

function EditorPremio({ p, onCerrar, onGuardado }: { p: any; onCerrar: () => void; onGuardado: () => void }) {
  const [f, setF] = useState<any>(p);
  const [error, setError] = useState("");
  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await (p.id ? apiP.put(`/crecimiento/premios/${p.id}`, f) : apiP.post("/crecimiento/premios", f)); onGuardado(); } catch (err: any) { setError(err.message); }
  };
  return (<Modal titulo={p.id ? "Editar premio" : "Nuevo premio"} onCerrar={onCerrar}><form onSubmit={guardar} className="space-y-3">
    <Aviso>{error}</Aviso>
    <label className="block"><span className="etiqueta">Texto que se muestra</span><input className="campo" required value={f.etiqueta} onChange={(e) => setF({ ...f, etiqueta: e.target.value })} placeholder="p. ej. 1 mes gratis" /></label>
    <div className="grid grid-cols-2 gap-3">
      <label><span className="etiqueta">Tipo</span><select className="campo" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>
        {Object.entries(TIPOS).filter(([k]) => f.lugar === "ruleta" || k !== "puntos").map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
      <label><span className="etiqueta">Cantidad</span><Num v={f.valor} set={(n: any) => setF({ ...f, valor: n ?? 0 })} /></label>
      {f.lugar === "ruleta" ? <><label><span className="etiqueta">Peso (probabilidad relativa)</span><Num v={f.peso} set={(n: any) => setF({ ...f, peso: n ?? 0 })} /></label>
        <label><span className="etiqueta">Tope al mes (vacío: sin tope)</span><Num v={f.tope_mensual} set={(n: any) => setF({ ...f, tope_mensual: n })} /></label>
        <label><span className="etiqueta">Orden en la ruleta</span><Num v={f.orden} set={(n: any) => setF({ ...f, orden: n ?? 0 })} /></label></>
        : <label><span className="etiqueta">Costo en puntos</span><Num v={f.costo} set={(n: any) => setF({ ...f, costo: n ?? 0 })} /></label>}
    </div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.activo} onChange={(e) => setF({ ...f, activo: e.target.checked })} /> Activo</label>
    <button className="btn-turquesa w-full">Guardar</button></form></Modal>);
}

function EditorPregunta({ p, onCerrar, onGuardado }: { p: any; onCerrar: () => void; onGuardado: () => void }) {
  const [f, setF] = useState<any>({ ...p, opciones: [...p.opciones] });
  const [error, setError] = useState("");
  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    const datos = { materia: f.materia, texto: f.texto, opciones: f.opciones.filter((o: string) => o.trim()), correcta: f.correcta, explicacion: f.explicacion, activa: f.activa };
    try { await (p.id ? apiP.put(`/crecimiento/preguntas/${p.id}`, datos) : apiP.post("/crecimiento/preguntas", datos)); onGuardado(); } catch (err: any) { setError(err.message); }
  };
  return (<Modal titulo={p.id ? "Editar pregunta" : "Nueva pregunta"} onCerrar={onCerrar} ancho="max-w-2xl"><form onSubmit={guardar} className="space-y-3">
    <Aviso>{error}</Aviso>
    <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
      <label><span className="etiqueta">Materia</span><input className="campo" required value={f.materia} onChange={(e) => setF({ ...f, materia: e.target.value })} /></label>
      <label><span className="etiqueta">Pregunta</span><input className="campo" required minLength={10} value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} /></label></div>
    <fieldset><legend className="etiqueta">Opciones (marque la correcta)</legend>
      {f.opciones.map((o: string, k: number) => (<div key={k} className="mt-1.5 flex items-center gap-2">
        <input type="radio" name="correcta" checked={f.correcta === k} onChange={() => setF({ ...f, correcta: k })} aria-label={`Opción ${k + 1} es la correcta`} />
        <input className="campo" value={o} onChange={(e) => { const ops = [...f.opciones]; ops[k] = e.target.value; setF({ ...f, opciones: ops }); }} placeholder={`Opción ${k + 1}`} /></div>))}</fieldset>
    <label className="block"><span className="etiqueta">Explicación con su fundamento (se muestra al contestar)</span><textarea className="campo" rows={3} required minLength={10} value={f.explicacion} onChange={(e) => setF({ ...f, explicacion: e.target.value })} /></label>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.activa} onChange={(e) => setF({ ...f, activa: e.target.checked })} /> Activa</label>
    <button className="btn-turquesa w-full">Guardar</button></form></Modal>);
}
