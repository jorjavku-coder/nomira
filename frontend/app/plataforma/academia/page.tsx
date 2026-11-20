"use client";
import { useCallback, useEffect, useState } from "react";
import ShellPlataforma, { useSesionP } from "@/components/plataforma";
import { Aviso, Modal } from "@/components/ui";
import { fecha, mxn } from "@/lib/api";
import { apiP, esSuperadmin } from "@/lib/plataforma";

const ORIGEN: Record<string, string> = { compra: "Compra en línea", comercial: "Cotización", cortesia: "Cortesía" };

/** Academia en el panel de Nomira: cuenta editora, catálogo con o sin costo, entregas y ajustes por despacho. */
export default function AcademiaPlataforma() {
  const sesion = useSesionP();
  const [r, setR] = useState<any>(null);
  const [conf, setConf] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [publicar, setPublicar] = useState<any>(null);
  const [entregar, setEntregar] = useState<any>(null);
  const [orgSel, setOrgSel] = useState("");
  const cargar = useCallback(() => apiP.get("/academia/config").then((x) => { setR(x); setConf(x.config); }).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(fn: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { const x = await fn(); if (x?.config) { setR(x); setConf(x.config); } setOk(x?.mensaje || msg); return true; } catch (e: any) { setError(e.message); return false; }
  }
  if (sesion && !esSuperadmin(sesion)) return <ShellPlataforma><Aviso>Solo un superadministrador puede administrar Academia.</Aviso></ShellPlataforma>;
  const pago = r?.catalogo.filter((c: any) => c.acceso === "pago" && c.estado === "publicado") || [];
  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Academia</h1>
      <p className="mb-4 mt-1 text-sm text-slate-500">Catálogo de cursos de Nomira (incluidos o con costo), cursos que entregas a despachos y límites por despacho. No ves los cursos internos de los despachos.</p>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {r && conf && <div className="space-y-6">
        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Configuración general</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[["cursos_incluidos", "Cursos propios incluidos"], ["cuota_medios_mb", "Espacio por despacho (MB)"], ["video_max_mb", "Video máximo (MB)"], ["scorm_max_mb", "SCORM máximo (MB)"]].map(([k, t]) => (
              <label key={k}><span className="etiqueta">{t}</span><input className="campo" type="number" min={0} value={conf[k]} onChange={(e) => setConf({ ...conf, [k]: Number(e.target.value) })} /></label>))}
            <label><span className="etiqueta">Cuenta editora del catálogo</span><select className="campo" value={conf.org_editora_id || ""} onChange={(e) => setConf({ ...conf, org_editora_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Sin elegir</option>{r.organizaciones.map((o: any) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select></label>
          </div>
          <p className="mt-2 text-xs text-slate-500">La cuenta editora es una organización de Nomira (por ejemplo, un cliente llamado «Nomira catálogo») donde armas los cursos con el editor normal de Academia: enlaces, Excel, SCORM o videos subidos. Si el despacho tiene un plan asignado en Comercial, Academia usa el almacenamiento de ese plan.</p>
          <button className="btn-turquesa mt-3" onClick={() => hacer(() => apiP.put("/academia/config", conf), "Configuración guardada.")}>Guardar</button>
        </section>

        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Cursos de la cuenta editora</h2>
          {!conf.org_editora_id ? <p className="mt-2 text-sm text-slate-500">Elige primero la cuenta editora.</p> : !r.editora.length ? <p className="mt-2 text-sm text-slate-500">La cuenta editora aún no tiene cursos. Entra a esa cuenta → Academia → Administrar y crea uno.</p> : (
            <ul className="mt-2 divide-y divide-crema-300">{r.editora.map((c: any) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <span><b className="text-marino">{c.titulo}</b> <span className="text-xs text-slate-500">· {c.lecciones} lecciones · {c.estado}</span>
                  {c.en_catalogo && <span className="block text-xs text-slate-600">En catálogo: {c.en_catalogo.acceso === "pago" ? `con costo ${mxn(c.en_catalogo.precio)} + IVA` : "incluido"} · versión {c.en_catalogo.version} · {c.en_catalogo.accesos} despacho(s) con acceso</span>}
                  {c.desactualizado && <span className="mt-1 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">Tiene cambios sin publicar en el catálogo</span>}</span>
                <span className="flex gap-2">
                  <button className="btn-sec py-1 text-xs" disabled={c.estado !== "publicado"} title={c.estado !== "publicado" ? "Publícalo primero en la cuenta editora" : ""}
                    onClick={() => setPublicar({ ...c, acceso: c.en_catalogo?.acceso || "incluido", precio: c.en_catalogo?.precio || "" })}>{c.en_catalogo ? "Actualizar en catálogo" : "Publicar en catálogo"}</button>
                  <button className="btn-sec py-1 text-xs" onClick={() => setEntregar({ ...c, organizacion_id: "" })}>Entregar a un despacho</button>
                </span>
              </li>))}</ul>)}
        </section>

        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Catálogo de Nomira (lo ven todos los despachos con Academia)</h2>
          <ul className="mt-2 divide-y divide-crema-300">{r.catalogo.map((c: any) => <CursoCatalogo key={c.id} c={c} hacer={hacer} />)}</ul>
        </section>

        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Por despacho</h2>
          <select className="campo mt-2 max-w-sm" aria-label="Despacho" value={orgSel} onChange={(e) => setOrgSel(e.target.value)}>
            <option value="">Elige un despacho…</option>{r.organizaciones.map((o: any) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select>
          {orgSel && <PorDespacho oid={Number(orgSel)} pago={pago} />}
        </section>
      </div>}

      {publicar && <Modal titulo={`Catálogo: ${publicar.titulo}`} onCerrar={() => setPublicar(null)}>
        <div className="space-y-3 text-sm">
          <label className="flex items-center gap-2"><input type="radio" className="accent-turquesa" checked={publicar.acceso === "incluido"} onChange={() => setPublicar({ ...publicar, acceso: "incluido" })} />Incluido para todos los despachos con Academia</label>
          <label className="flex items-center gap-2"><input type="radio" className="accent-turquesa" checked={publicar.acceso === "pago"} onChange={() => setPublicar({ ...publicar, acceso: "pago" })} />Con costo (pago único por despacho)</label>
          {publicar.acceso === "pago" && <label className="block"><span className="etiqueta">Precio antes de IVA (MXN)</span><input className="campo" inputMode="decimal" value={publicar.precio} onChange={(e) => setPublicar({ ...publicar, precio: e.target.value })} /></label>}
          <p className="text-xs text-slate-500">Se copia el contenido actual del curso. Quien ya lo empezó conserva su avance; las lecciones quitadas se archivan.</p>
        </div>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setPublicar(null)}>Cancelar</button>
          <button className="btn-turquesa" onClick={async () => { if (await hacer(() => apiP.post(`/academia/editora/${publicar.id}/publicar`, { acceso: publicar.acceso, precio: publicar.acceso === "pago" ? publicar.precio : null }), "Catálogo actualizado.")) setPublicar(null); }}>Publicar</button></div>
      </Modal>}
      {entregar && <Modal titulo={`Entregar «${entregar.titulo}»`} onCerrar={() => setEntregar(null)}>
        <label className="block"><span className="etiqueta">Despacho</span><select className="campo" value={entregar.organizacion_id} onChange={(e) => setEntregar({ ...entregar, organizacion_id: e.target.value })}>
          <option value="">Elige…</option>{r.organizaciones.filter((o: any) => o.id !== conf.org_editora_id).map((o: any) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select></label>
        <p className="mt-2 text-xs text-slate-500">Se copia como <b>borrador</b> en la Academia del despacho; ellos lo revisan y publican. Cuenta para su límite de cursos propios.</p>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setEntregar(null)}>Cancelar</button>
          <button className="btn-turquesa" disabled={!entregar.organizacion_id} onClick={async () => { if (await hacer(() => apiP.post(`/academia/editora/${entregar.id}/entregar`, { organizacion_id: Number(entregar.organizacion_id) }), "Curso entregado.")) setEntregar(null); }}>Entregar</button></div>
      </Modal>}
    </ShellPlataforma>
  );
}

function CursoCatalogo({ c, hacer }: { c: any; hacer: any }) {
  const [d, setD] = useState({ acceso: c.acceso, precio: c.precio || "" });
  return (
    <li className={`flex flex-wrap items-center justify-between gap-2 py-3 text-sm ${c.estado === "archivado" ? "opacity-60" : ""}`}>
      <span><b className="text-marino">{c.titulo}</b> <span className="text-xs text-slate-500">· {c.lecciones} lecciones · v{c.version}{c.semilla ? " · curso base" : ""} · {c.accesos} con acceso pagado/otorgado{c.estado === "archivado" ? " · archivado" : ""}</span></span>
      <span className="flex flex-wrap items-center gap-2">
        <select className="campo w-auto py-1" aria-label={`Acceso de ${c.titulo}`} value={d.acceso} onChange={(e) => setD({ ...d, acceso: e.target.value })}><option value="incluido">Incluido</option><option value="pago">Con costo</option></select>
        {d.acceso === "pago" && <input className="campo w-28 py-1" inputMode="decimal" placeholder="Precio" aria-label={`Precio de ${c.titulo}`} value={d.precio} onChange={(e) => setD({ ...d, precio: e.target.value })} />}
        <button className="btn-sec py-1 text-xs" onClick={() => hacer(() => apiP.patch(`/academia/catalogo/${c.id}`, { acceso: d.acceso, precio: d.acceso === "pago" ? d.precio : null, estado: c.estado }), "Curso actualizado.")}>Guardar</button>
        <button className="btn-sec py-1 text-xs" onClick={() => hacer(() => apiP.patch(`/academia/catalogo/${c.id}`, { acceso: c.acceso, precio: c.precio, estado: c.estado === "archivado" ? "publicado" : "archivado" }), c.estado === "archivado" ? "Curso visible de nuevo." : "Curso archivado (el avance se conserva).")}>{c.estado === "archivado" ? "Restaurar" : "Archivar"}</button>
      </span>
    </li>
  );
}

function PorDespacho({ oid, pago }: { oid: number; pago: any[] }) {
  const [o, setO] = useState<any>(null);
  const [d, setD] = useState<any>(null);
  const [curso, setCurso] = useState("");
  const [msg, setMsg] = useState(""); const [error, setError] = useState("");
  const cargar = useCallback(() => apiP.get(`/academia/organizaciones/${oid}`).then((x) => { setO(x); setD({ ac_cursos_extra: x.ac_cursos_extra, ac_cuota_medios_mb: x.ac_cuota_medios_mb ?? "" }); }).catch((e) => setError(e.message)), [oid]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(fn: () => Promise<any>, m: string) { setMsg(""); setError(""); try { const x = await fn(); setO(x); setMsg(m); } catch (e: any) { setError(e.message); } }
  if (!o) return <p className="mt-3 text-sm text-slate-500">{error || "Cargando…"}</p>;
  return (
    <div className="mt-4 grid gap-5 lg:grid-cols-2">
      <div>
        <p className="text-sm">Cursos propios: <b>{o.limite.usados} de {o.limite.limite}</b> ({o.limite.incluidos} incluidos + {o.limite.adicionales} adicionales)</p>
        <p className="text-sm">{o.espacio.alcance === "despacho" ? "Almacenamiento de su plan (todo el despacho)" : "Espacio para videos y SCORM"}: <b>{o.espacio.usado_mb} de {o.espacio.cuota_mb} MB</b></p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <label><span className="etiqueta">Cursos adicionales</span><input className="campo" type="number" min={0} value={d.ac_cursos_extra} onChange={(e) => setD({ ...d, ac_cursos_extra: Number(e.target.value) })} /></label>
          <label><span className="etiqueta">Espacio fijo para Academia (MB, vacío = el de su plan)</span><input className="campo" type="number" min={0} value={d.ac_cuota_medios_mb} onChange={(e) => setD({ ...d, ac_cuota_medios_mb: e.target.value })} /></label>
        </div>
        <button className="btn-sec mt-2" onClick={() => hacer(() => apiP.patch(`/academia/organizaciones/${oid}`, { ac_cursos_extra: d.ac_cursos_extra, ac_cuota_medios_mb: d.ac_cuota_medios_mb === "" ? null : Number(d.ac_cuota_medios_mb) }), "Ajustes guardados.")}>Guardar ajustes</button>
        <p className="mt-1 text-xs text-slate-500">Para cobrar cursos adicionales, inclúyelos en una cotización de Comercial: al asignarla se actualiza solo.</p>
      </div>
      <div>
        <h3 className="text-sm font-semibold text-marino">Cursos de Nomira con costo a los que tiene acceso</h3>
        <ul className="mt-1 space-y-1 text-sm">{o.accesos.length ? o.accesos.map((a: any) => (
          <li key={a.curso_id} className={a.revocado_en ? "text-slate-400 line-through" : ""}>{a.curso} · {ORIGEN[a.origen]} · {fecha(a.creado_en)}
            {!a.revocado_en && <button className="ml-2 text-xs font-semibold text-red-700 hover:underline" onClick={() => hacer(() => apiP.borrar(`/academia/organizaciones/${oid}/accesos/${a.curso_id}`), "Acceso retirado (el avance se conserva).")}>Retirar</button>}</li>))
          : <li className="text-slate-500">Ninguno.</li>}</ul>
        {pago.length > 0 && <div className="mt-2 flex gap-2"><select className="campo" aria-label="Curso de cortesía" value={curso} onChange={(e) => setCurso(e.target.value)}>
          <option value="">Dar acceso de cortesía…</option>{pago.map((c: any) => <option key={c.id} value={c.id}>{c.titulo}</option>)}</select>
          <button className="btn-sec" disabled={!curso} onClick={() => hacer(() => apiP.post(`/academia/organizaciones/${oid}/accesos`, { curso_id: Number(curso) }), "Acceso otorgado.")}>Dar acceso</button></div>}
      </div>
      <div className="lg:col-span-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{msg}</Aviso></div>
    </div>
  );
}
