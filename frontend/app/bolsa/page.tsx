"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { ESTADO_VACANTE, EditorPrueba, FormVacante, Premium, VistaPrueba, copiar } from "@/components/bolsa";
import { Aviso, ConfirmarEliminar } from "@/components/ui";
import { api } from "@/lib/api";

export default function Bolsa() {
  const [cfg, setCfg] = useState<any>(null);
  const [vs, setVs] = useState<any[] | null>(null);
  const [cat, setCat] = useState<any>(null);
  const [tab, setTab] = useState<"vacantes" | "pruebas" | "pagina">("vacantes");
  const [dialogo, setDialogo] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const cargar = useCallback(() => {
    api.get("/bolsa/config").then(setCfg).catch((e) => setError(e.message));
    api.get("/bolsa/vacantes").then((r) => setVs(r.vacantes)).catch((e) => setError(e.message));
    api.get("/bolsa/pruebas").then(setCat).catch(() => {});
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  async function accion(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await f(); setOk(msg); cargar(); } catch (e: any) { setError(e.message); }
  }
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Reclutamiento</p>
          <h1 className="text-3xl font-extrabold text-marino">Bolsa de trabajo</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Publica vacantes gratis en tu página de empleos y en la bolsa de Nomira, recibe CVs y da seguimiento a cada candidato.</p></div>
        <div className="flex flex-wrap items-center gap-2"><BotonAyuda modulo="bolsa" />
          {cfg?.puede_editar && <button className="btn-turquesa" onClick={() => setDialogo({ tipo: "vacante" })}>+ Nueva vacante</button>}</div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mb-4 flex flex-wrap gap-2" role="tablist">
        {([["vacantes", "Vacantes"], ["pruebas", "Pruebas psicométricas"], ["pagina", "Mi página de empleos"]] as const).map(([k, t]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === k ? "bg-marino text-white" : "bg-crema text-marino hover:bg-crema-300"}`}>{t}</button>))}
      </div>

      {tab === "vacantes" && <section className="tarjeta overflow-hidden" aria-label="Vacantes">
        {vs && !vs.length && <div className="p-8 text-center">
          <p className="text-lg font-semibold text-marino">Todavía no tienes vacantes</p>
          <p className="mt-1 text-sm text-slate-600">Crea la primera: queda como borrador hasta que la publiques.</p></div>}
        {vs && vs.length > 0 && <table className="w-full text-sm">
          <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
            <th className="px-4 py-2">Vacante</th><th className="px-4 py-2">Estado</th><th className="px-4 py-2">Candidatos</th><th className="px-4 py-2"><span className="sr-only">Acciones</span></th></tr></thead>
          <tbody className="divide-y divide-crema-200">{vs.map((v) => (
            <tr key={v.id}>
              <td className="px-4 py-3"><Link href={`/bolsa/${v.id}`} className="font-semibold text-marino hover:underline">{v.titulo}</Link>
                <span className="block text-xs text-slate-500">{v.area_texto} · {v.modalidad_texto}{v.estado_republica ? ` · ${v.estado_republica}` : ""}</span></td>
              <td className="px-4 py-3"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_VACANTE[v.estado][1]}`}>{ESTADO_VACANTE[v.estado][0]}</span>
                {v.estado === "publicada" && !v.en_portal && <span className="block text-xs text-slate-500">Solo en tu página</span>}</td>
              <td className="px-4 py-3">{v.candidatos}{v.nuevos > 0 && <span className="ml-2 rounded-full bg-turquesa px-2 py-0.5 text-xs font-bold text-white">{v.nuevos} nuevo{v.nuevos === 1 ? "" : "s"}</span>}</td>
              <td className="px-4 py-3 text-right text-xs">
                {cfg?.puede_editar && v.estado !== "publicada" && v.estado !== "cerrada" && <button className="font-semibold text-turquesa-700 underline"
                  onClick={() => accion(() => api.post(`/bolsa/vacantes/${v.id}/estado`, { estado: "publicada" }), "Vacante publicada.")}>Publicar</button>}
                {v.estado === "publicada" && <button className="font-semibold text-turquesa-700 underline" onClick={async () => setOk((await copiar(v.url)) ? "Enlace copiado: compártelo en redes o por WhatsApp." : v.url)}>Copiar enlace</button>}
              </td>
            </tr>))}</tbody></table>}
      </section>}

      {tab === "pruebas" && cat && <section className="space-y-4" aria-label="Pruebas psicométricas">
        {!cat.premium && <Premium texto="Manda a tus candidatos pruebas de personalidad, razonamiento, atención y conocimientos jurídicos, o arma tus propios exámenes. Se califican solas y ves los resultados junto a cada candidato." />}
        {[...new Set<string>(cat.nomira.map((p: any) => p.categoria))].map((g) => (
          <div key={g} className="tarjeta p-4"><h2 className="font-semibold text-marino">{g}</h2>
            {g === "Conocimientos jurídicos" && <p className="text-xs text-slate-500">Preguntas revisadas a {cat.revision_juridica}. Si cambia la ley o quieres ajustarlas, cópialas a tus pruebas y edítalas.</p>}
            <ul className="mt-2 divide-y divide-crema-200">{cat.nomira.filter((p: any) => p.categoria === g).map((p: any) => (
              <li key={p.clave} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span><b className="text-marino">{p.nombre}</b><span className="block text-xs text-slate-500">{p.descripcion} · {p.minutos} min</span></span>
                <span className="flex gap-3 text-xs"><button className="font-semibold text-turquesa-700 underline" onClick={() => setDialogo({ tipo: "ver", clave: p.clave })}>Ver preguntas</button>
                  {cat.premium && cfg?.puede_editar && p.tipo === "opcion" && <button className="text-slate-600 underline" onClick={() => accion(() => api.post(`/bolsa/pruebas/copiar/${p.clave}`), "Copiada a las pruebas de tu despacho.")}>Copiar y editar</button>}</span>
              </li>))}</ul></div>))}
        <div className="tarjeta p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold text-marino">Pruebas de tu despacho</h2>
          {cat.premium && cfg?.puede_editar && <button className="btn-sec" onClick={() => setDialogo({ tipo: "editor" })}>+ Nueva prueba</button>}</div>
          {cat.propias.length ? <ul className="mt-2 divide-y divide-crema-200">{cat.propias.map((p: any) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span><b className="text-marino">{p.nombre}</b>{!p.activa && <span className="ml-2 text-xs text-slate-500">(desactivada)</span>}
                <span className="block text-xs text-slate-500">{p.preguntas} preguntas{p.minutos ? ` · ${p.minutos} min` : ""}</span></span>
              <span className="flex gap-3 text-xs"><button className="font-semibold text-turquesa-700 underline" onClick={() => setDialogo({ tipo: "ver", clave: p.clave })}>Ver</button>
                {cat.premium && cfg?.puede_editar && <button className="text-slate-600 underline" onClick={async () => {
                  const d = await api.get(`/bolsa/pruebas/ver/${p.clave}`); setDialogo({ tipo: "editor", prueba: { ...d, id: p.id } }); }}>Editar</button>}
                {cfg?.puede_editar && <button className="text-slate-500 underline" onClick={() => setDialogo({ tipo: "borrar_prueba", prueba: p })}>Borrar</button>}</span>
            </li>))}</ul> : <p className="mt-1 text-sm text-slate-500">Arma tu propio examen con preguntas de opción múltiple (se califican solas) o abiertas.</p>}
        </div>
      </section>}

      {tab === "pagina" && cfg && <PaginaEmpleos cfg={cfg} onGuardado={(p) => { setCfg({ ...cfg, perfil: p }); setOk("Página actualizada."); }} />}

      {dialogo?.tipo === "vacante" && <FormVacante cfg={cfg} onCerrar={() => setDialogo(null)} onListo={(v) => { setDialogo(null); window.location.href = `/bolsa/${v.id}`; }} />}
      {dialogo?.tipo === "ver" && <VistaPrueba clave={dialogo.clave} onCerrar={() => setDialogo(null)} />}
      {dialogo?.tipo === "editor" && <EditorPrueba prueba={dialogo.prueba} onCerrar={() => setDialogo(null)} onListo={() => { setDialogo(null); setOk("Prueba guardada."); cargar(); }} />}
      {dialogo?.tipo === "borrar_prueba" && <ConfirmarEliminar titulo="Borrar prueba" onCerrar={() => setDialogo(null)}
        onConfirmar={() => api.borrar(`/bolsa/pruebas/propias/${dialogo.prueba.id}`).then(() => cargar())}>
        ¿Borrar «{dialogo.prueba.nombre}»? Si ya la contestó alguien, solo se desactiva para conservar sus resultados.</ConfirmarEliminar>}
    </Shell>
  );
}

function PaginaEmpleos({ cfg, onGuardado }: { cfg: any; onGuardado: (p: any) => void }) {
  const [f, setF] = useState({ nombre_publico: cfg.perfil.nombre_publico || "", descripcion: cfg.perfil.descripcion || "", ciudad: cfg.perfil.ciudad || "",
    sitio_web: cfg.perfil.sitio_web || "", correo_privacidad: cfg.perfil.correo_privacidad || "" });
  const [error, setError] = useState("");
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { onGuardado(await api.put("/bolsa/perfil", { ...f, descripcion: f.descripcion || null, ciudad: f.ciudad || null, sitio_web: f.sitio_web || null, correo_privacidad: f.correo_privacidad || null })); }
    catch (er: any) { setError(er.message); }
  }
  return (
    <section className="tarjeta p-5" aria-label="Mi página de empleos">
      <p className="text-sm text-slate-600">Tu página pública con todas tus vacantes publicadas:</p>
      <p className="mt-1 flex flex-wrap items-center gap-3"><a href={cfg.perfil.url} target="_blank" rel="noopener noreferrer" className="break-all font-semibold text-turquesa-700 underline">{cfg.perfil.url}</a>
        <button className="btn-sec text-sm" onClick={() => copiar(cfg.perfil.url)}>Copiar</button></p>
      <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={guardar}>
        <label className="block sm:col-span-2"><span className="etiqueta">Nombre que verán los candidatos</span><input className="campo" value={f.nombre_publico} onChange={pon("nombre_publico")} disabled={!cfg.es_admin} required minLength={2} /></label>
        <label className="block sm:col-span-2"><span className="etiqueta">Sobre el despacho</span><textarea className="campo min-h-24" value={f.descripcion} onChange={pon("descripcion")} disabled={!cfg.es_admin} maxLength={3000} /></label>
        <label className="block"><span className="etiqueta">Ciudad</span><input className="campo" value={f.ciudad} onChange={pon("ciudad")} disabled={!cfg.es_admin} /></label>
        <label className="block"><span className="etiqueta">Sitio web</span><input className="campo" value={f.sitio_web} onChange={pon("sitio_web")} disabled={!cfg.es_admin} placeholder="https://" /></label>
        <label className="block sm:col-span-2"><span className="etiqueta">Correo para dudas de privacidad de los candidatos</span>
          <input className="campo" type="email" value={f.correo_privacidad} onChange={pon("correo_privacidad")} disabled={!cfg.es_admin} />
          <span className="text-xs text-slate-500">Aparece en el aviso que aceptan al postularse, para que puedan pedir que borres sus datos.</span></label>
        <Aviso>{error}</Aviso>
        {cfg.es_admin && <div className="sm:col-span-2"><button className="btn-turquesa">Guardar página</button></div>}
      </form>
    </section>
  );
}
