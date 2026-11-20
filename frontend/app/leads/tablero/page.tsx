"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { LeadsShell, ProximoPaso, recargarCatalogosLeads, useCatalogosLeads } from "@/components/leads";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

/** Seguimiento visual: una columna por etapa. Se arrastra la tarjeta (escritorio) o se usa «Mover a…» (celular). */
export default function Tablero() {
  const cat = useCatalogosLeads();
  const router = useRouter();
  const [t, setT] = useState<any>(null);
  const [f, setF] = useState<any>({ responsable_id: "", materia: "", canal: "" });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [mover, setMover] = useState<any>(null);
  const [etapas, setEtapas] = useState(false);
  const [arrastrando, setArrastrando] = useState<number | null>(null);
  const cargar = useCallback(() => {
    const q = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]).toString();
    api.get(`/leads/tablero?${q}`).then(setT).catch((e) => setError(e.message));
  }, [f]);
  useEffect(() => { cargar(); }, [cargar]);

  function pedirMovimiento(tarjeta: any, etapaId: number) {
    const e = cat.etapas.find((x: any) => x.id === etapaId);
    if (!e || e.id === tarjeta.etapa_id) return;
    if (e.tipo === "ganada") { router.push(`/leads/prospectos/${tarjeta.id}`); return; }
    setMover({ tarjeta, etapa: e });
  }
  async function confirmar(nota: string, motivo: string) {
    setError(""); setOk("");
    try {
      await api.post(`/leads/prospectos/${mover.tarjeta.id}/etapa`, { etapa_id: mover.etapa.id, nota: nota || null, motivo: motivo || null });
      setOk(`${mover.tarjeta.nombre} pasó a «${mover.etapa.nombre}».`);
      setMover(null);
      cargar();
    } catch (e: any) { setError(e.message); }
  }
  return (
    <LeadsShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Seguimiento</h1>
          <p className="text-sm text-slate-500">Arrastre una tarjeta a otra etapa o use «Mover a…». Los cerrados se muestran 60 días.</p></div>
        {cat?.es_admin && <button className="btn-sec" onClick={() => setEtapas(true)}>Personalizar etapas</button>}
      </div>
      {cat && (
        <div className="mb-4 flex flex-wrap gap-2">
          <select className="campo w-auto" value={f.responsable_id} onChange={(e) => setF({ ...f, responsable_id: e.target.value })} aria-label="Responsable">
            <option value="">Todos los responsables</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select>
          <select className="campo w-auto" value={f.materia} onChange={(e) => setF({ ...f, materia: e.target.value })} aria-label="Materia">
            <option value="">Todas las materias</option>{cat.materias.map((x: string) => <option key={x}>{x}</option>)}</select>
          <select className="campo w-auto" value={f.canal} onChange={(e) => setF({ ...f, canal: e.target.value })} aria-label="Canal">
            <option value="">Todos los canales</option>{Object.entries(cat.canales).map(([k, x]: any) => <option key={k} value={k}>{x}</option>)}</select>
        </div>)}
      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {!t && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {t && cat && (
        <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-4">
          {t.columnas.map((c: any) => (
            <section key={c.id} className={`w-72 shrink-0 snap-start rounded-2xl border p-2 ${c.tipo === "ganada" ? "border-emerald-200 bg-emerald-50/40" : c.tipo === "perdida" ? "border-slate-200 bg-slate-50" : "border-crema-300 bg-crema/60"} ${arrastrando ? "ring-2 ring-turquesa/0 hover:ring-turquesa/40" : ""}`}
              onDragOver={(e) => { if (cat.puede_editar) e.preventDefault(); }}
              onDrop={() => { const x = t.columnas.flatMap((k: any) => k.tarjetas).find((k: any) => k.id === arrastrando); setArrastrando(null); if (x) pedirMovimiento(x, c.id); }}
              aria-label={`Etapa ${c.nombre}`}>
              <h2 className="flex items-center justify-between px-2 py-1.5 text-sm font-bold text-marino">{c.nombre}<span className="rounded-full bg-white px-2 text-xs text-slate-500">{c.total}</span></h2>
              <div className="space-y-2">
                {c.tarjetas.length === 0 && <p className="px-2 py-4 text-center text-xs text-slate-400">Sin prospectos</p>}
                {c.tarjetas.map((x: any) => (
                  <article key={x.id} draggable={cat.puede_editar} onDragStart={() => setArrastrando(x.id)} onDragEnd={() => setArrastrando(null)}
                    className="tarjeta cursor-grab p-3 text-sm active:cursor-grabbing">
                    <Link href={`/leads/prospectos/${x.id}`} className="font-semibold text-marino hover:underline">{x.nombre}</Link>
                    <p className="truncate text-xs text-slate-500">{[x.materia, x.canal_texto].filter(Boolean).join(" · ")}</p>
                    <p className="mt-1 text-xs">{c.tipo === "abierta" ? <ProximoPaso p={x.proxima} /> : c.tipo === "perdida" ? `Motivo: ${x.motivo_perdida || "—"}` : "Contratado"}</p>
                    <p className="text-xs text-slate-500">{x.responsable || "Sin responsable"}</p>
                    {cat.puede_editar && (
                      <select className="campo mt-2 py-1 text-xs" value="" aria-label={`Mover a ${x.nombre}`} onChange={(e) => pedirMovimiento(x, Number(e.target.value))}>
                        <option value="">Mover a…</option>
                        {cat.etapas.filter((e: any) => e.id !== x.etapa_id).map((e: any) => <option key={e.id} value={e.id}>{e.nombre}</option>)}</select>)}
                  </article>))}
              </div>
            </section>))}
        </div>)}
      {mover && <ConfirmarMovimiento mover={mover} motivos={cat.motivos} onCerrar={() => setMover(null)} onConfirmar={confirmar} />}
      {etapas && <EditarEtapas onCerrar={() => { setEtapas(false); cargar(); }} />}
    </LeadsShell>
  );
}

function ConfirmarMovimiento({ mover, motivos, onCerrar, onConfirmar }: any) {
  const [nota, setNota] = useState("");
  const [motivo, setMotivo] = useState("");
  const perdida = mover.etapa.tipo === "perdida";
  return (
    <Modal titulo={`Mover a «${mover.etapa.nombre}»`} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onConfirmar(nota, motivo); }}>
        <p className="text-sm text-slate-600"><b>{mover.tarjeta.nombre}</b> · de «{mover.tarjeta.etapa}» a «{mover.etapa.nombre}».</p>
        {perdida && <select className="campo" required value={motivo} onChange={(e) => setMotivo(e.target.value)} aria-label="Motivo">
          <option value="">¿Por qué no se contrató o no se atendió?</option>{motivos.map((x: string) => <option key={x}>{x}</option>)}</select>}
        <input className="campo" maxLength={500} autoFocus placeholder="Nota breve (opcional)" value={nota} onChange={(e) => setNota(e.target.value)} />
        <div className="flex justify-end"><button className="btn-turquesa">Mover</button></div>
      </form>
    </Modal>
  );
}

function EditarEtapas({ onCerrar }: { onCerrar: () => void }) {
  const cat = useCatalogosLeads();
  const [error, setError] = useState("");
  const [nueva, setNueva] = useState("");
  const [nombres, setNombres] = useState<Record<number, string>>({});
  const etapas = cat?.etapas || [];
  const abiertas = etapas.filter((e: any) => e.tipo === "abierta");
  async function hacer(fn: () => Promise<any>) {
    setError("");
    try { await fn(); await recargarCatalogosLeads(); } catch (e: any) { setError(e.message); }
  }
  const mover = (i: number, d: number) => {
    const ids = abiertas.map((e: any) => e.id);
    const j = i + d;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    hacer(() => api.post("/leads/etapas/orden", { ids }));
  };
  return (
    <Modal titulo="Personalizar etapas" onCerrar={onCerrar}>
      <div className="space-y-2">
        <Aviso>{error}</Aviso>
        {etapas.map((e: any) => {
          const i = abiertas.findIndex((x: any) => x.id === e.id);
          return (
            <div key={e.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-crema-300 p-2">
              <input className="campo min-w-0 flex-1 py-1.5" value={nombres[e.id] ?? e.nombre} onChange={(x) => setNombres({ ...nombres, [e.id]: x.target.value })}
                onBlur={() => nombres[e.id] && nombres[e.id] !== e.nombre && hacer(() => api.patch(`/leads/etapas/${e.id}`, { nombre: nombres[e.id] }))} aria-label={`Nombre de ${e.nombre}`} />
              {e.tipo === "abierta" ? <>
                <button className="btn-sec px-2 py-1 text-xs" disabled={i === 0} onClick={() => mover(i, -1)} aria-label="Subir">↑</button>
                <button className="btn-sec px-2 py-1 text-xs" disabled={i === abiertas.length - 1} onClick={() => mover(i, 1)} aria-label="Bajar">↓</button>
                <button className="btn-peligro px-2 py-1 text-xs" onClick={() => hacer(() => api.patch(`/leads/etapas/${e.id}`, { archivada: true }))}>Quitar</button>
              </> : <span className="text-xs text-slate-500">{e.tipo === "ganada" ? "Cierre: contratado" : "Cierre: no contratado"}</span>}
            </div>);
        })}
        <form className="flex gap-2 pt-2" onSubmit={(e) => { e.preventDefault(); hacer(() => api.post("/leads/etapas", { nombre: nueva })).then(() => setNueva("")); }}>
          <input className="campo" placeholder="Nueva etapa (p. ej. Documentos recibidos)" minLength={2} required value={nueva} onChange={(e) => setNueva(e.target.value)} />
          <button className="btn-turquesa whitespace-nowrap">Agregar</button>
        </form>
        <p className="text-xs text-slate-500">Solo se puede quitar una etapa vacía. Los cambios quedan registrados.</p>
      </div>
    </Modal>
  );
}
