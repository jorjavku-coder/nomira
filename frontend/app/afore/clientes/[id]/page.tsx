"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AforeShell, COLOR_CASO, Pastilla, useCatalogos } from "@/components/afore";
import { useSesion } from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

export default function ClienteAfore() {
  const { id } = useParams<{ id: string }>();
  const cat = useCatalogos();
  const sesion = useSesion();
  const editor = !!sesion && sesion.usuario.rol !== "consulta";
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [revelado, setRevelado] = useState<Record<string, any>>({});
  const [editar, setEditar] = useState(false);
  const [enlace, setEnlace] = useState<any>(null);
  const [acc, setAcc] = useState({ dias: 7, requiere_codigo: true });
  const cargar = useCallback(() => api.get(`/afore/clientes/${id}`).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function accion(fn: () => Promise<any>, mensaje = "") {
    setError(""); setOk("");
    try { const r = await fn(); if (mensaje) setOk(mensaje); await cargar(); return r ?? true; } catch (e: any) { setError(e.message); }
  }
  if (!c || !cat) return <AforeShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AforeShell>;
  const revelar = async (campo: string) => { try { setRevelado({ ...revelado, [campo]: await api.post(`/afore/clientes/${id}/revelar`, { campo }) }); } catch (e: any) { setError(e.message); } };
  return (
    <AforeShell>
      <Link href="/afore/clientes" className="text-sm text-turquesa-700 hover:underline">← Clientes</Link>
      <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">{c.nombre}</h1>
          <p className="text-sm text-slate-600">{c.relacion_texto} · titular: {c.titular_estado_texto} · prefiere: {cat.contacto[c.preferencia_contacto]}</p></div>
        {editor && <div className="flex gap-2"><button className="btn-sec" onClick={() => setEditar(true)}>Editar datos</button>
          <Link className="btn-turquesa" href={`/afore/casos/nuevo?cliente=${c.id}`}>+ Nuevo caso</Link></div>}
      </div>
      <div className="mt-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <section className="tarjeta p-5">
          <h2 className="mb-3 font-semibold text-marino">Datos de contacto e identificación</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">Teléfono</dt><dd>{c.telefono || "—"}</dd>
            <dt className="text-slate-500">Correo</dt><dd>{c.email || "—"}</dd>
            {(["curp", "nss"] as const).map((k) => <><dt key={k + "t"} className="text-slate-500">{k.toUpperCase()}</dt>
              <dd key={k} className="font-mono">{revelado[k]?.valor || c[k] || "—"}
                {c[k] && !revelado[k] && editor && <button className="ml-2 font-sans text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => revelar(k)}>Mostrar completo</button>}
                {revelado[k]?.revision && <div className={`font-sans text-xs ${revelado[k].revision.valida_formato ? "text-emerald-700" : "text-amber-700"}`}>{revelado[k].revision.detalle}</div>}</dd></>)}
          </dl>
          <p className="mt-3 text-xs text-slate-500">CURP y NSS se guardan cifrados. Mostrarlos completos queda registrado en la bitácora.</p>
          {c.notas && <p className="mt-3 rounded-lg bg-crema/70 p-3 text-sm"><b>Notas internas:</b> {c.notas}</p>}
        </section>
        <section className="tarjeta p-5">
          <h2 className="mb-3 font-semibold text-marino">Consentimiento para recibir actualizaciones</h2>
          <ul className="space-y-2 text-sm">
            {c.consentimientos.length === 0 && <li className="text-slate-500">Sin consentimientos registrados. No se le enviará ningún mensaje.</li>}
            {c.consentimientos.map((x: any) => (
              <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-crema-300 p-2.5">
                <span><b>{x.canal === "whatsapp" ? "WhatsApp" : "Correo"}</b> · {x.alcance}<span className="block text-xs text-slate-500">Otorgado {fechaHora(x.otorgado_en)} ({x.medio}){x.revocado_en && ` · revocado ${fechaHora(x.revocado_en)} (${x.revocado_medio})`}</span></span>
                {x.revocado_en ? <Pastilla clase="bg-slate-200 text-slate-600">Revocado</Pastilla> : editor && <button className="text-xs font-semibold text-red-700 hover:underline" onClick={() => accion(() => api.post(`/afore/consentimientos/${x.id}/revocar`), "Consentimiento revocado.")}>Revocar</button>}
              </li>))}
          </ul>
          {editor && <div className="mt-3 flex flex-wrap gap-2">
            {!c.consiente.whatsapp && <button className="btn-sec" disabled={!c.telefono} onClick={() => accion(() => api.post(`/afore/clientes/${id}/consentimientos`, { canal: "whatsapp", medio: prompt("¿Cómo lo otorgó? (verbal, escrito…)", "verbal") || "verbal" }), "Consentimiento registrado.")}>Registrar consentimiento WhatsApp</button>}
            {!c.consiente.correo && <button className="btn-sec" disabled={!c.email} onClick={() => accion(() => api.post(`/afore/clientes/${id}/consentimientos`, { canal: "correo", medio: prompt("¿Cómo lo otorgó? (verbal, escrito…)", "verbal") || "verbal" }), "Consentimiento registrado.")}>Registrar consentimiento correo</button>}
          </div>}
        </section>
        <section className="tarjeta p-5">
          <h2 className="mb-1 font-semibold text-marino">Portal seguro del cliente</h2>
          <p className="mb-3 text-sm text-slate-500">Genere un enlace con vencimiento para que el cliente vea lo que usted comparta y envíe documentos. El enlace no contiene información del caso.</p>
          {editor && <div className="flex flex-wrap items-end gap-2">
            <label className="block"><span className="etiqueta">Vence en</span><select className="campo w-auto" value={acc.dias} onChange={(e) => setAcc({ ...acc, dias: Number(e.target.value) })}>
              {[1, 3, 7, 14, 30].map((x) => <option key={x} value={x}>{x} día(s)</option>)}</select></label>
            <label className="mb-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={acc.requiere_codigo && !!c.email} disabled={!c.email} onChange={(e) => setAcc({ ...acc, requiere_codigo: e.target.checked })} /> Pedir código enviado a su correo</label>
            <button className="btn-turquesa" onClick={async () => { const r = await accion(() => api.post(`/afore/clientes/${id}/acceso`, { ...acc, requiere_codigo: acc.requiere_codigo && !!c.email }), "Enlace creado."); if (r && r !== true) setEnlace(r); }}>Generar enlace</button>
          </div>}
          <ul className="mt-3 space-y-1 text-xs text-slate-600">{c.accesos.map((a: any) => (
            <li key={a.id} className="flex justify-between gap-2"><span>Enlace …{a.pista} · {a.estado} · vence {fechaHora(a.expira_en)}{a.ultimo_uso_en && ` · usado ${fechaHora(a.ultimo_uso_en)}`}</span>
              {a.estado === "activo" && editor && <button className="font-semibold text-red-700 hover:underline" onClick={() => accion(() => api.post(`/afore/accesos/${a.id}/revocar`), "Enlace revocado.")}>Revocar</button>}</li>))}</ul>
        </section>
        <section className="tarjeta p-5">
          <h2 className="mb-3 font-semibold text-marino">Casos</h2>
          {c.casos.length === 0 ? <p className="text-sm text-slate-500">Sin casos.</p> : <ul className="space-y-2">{c.casos.map((x: any) => (
            <li key={x.id}><Link className="flex items-center justify-between gap-2 rounded-lg border border-crema-300 p-2.5 text-sm hover:border-turquesa" href={`/afore/casos/${x.id}`}>
              <span>{x.tipo_texto}</span><Pastilla clase={COLOR_CASO[x.estado]}>{x.estado_texto}</Pastilla></Link></li>))}</ul>}
        </section>
      </div>
      {enlace && (
        <Modal titulo="Enlace al portal del cliente" onCerrar={() => setEnlace(null)}>
          <p className="mb-2 text-sm">Se muestra <b>solo esta vez</b>. Compártalo únicamente con el cliente (por ejemplo, desde un mensaje aprobado). Vence el {fechaHora(enlace.expira_en)}.</p>
          <input className="campo font-mono text-xs" readOnly value={enlace.enlace} onFocus={(e) => e.target.select()} />
          <div className="mt-3 flex justify-end gap-2"><button className="btn-sec" onClick={() => navigator.clipboard?.writeText(enlace.enlace)}>Copiar</button><button className="btn-primario" onClick={() => setEnlace(null)}>Listo</button></div>
        </Modal>
      )}
      {editar && <EditarCliente c={c} cat={cat} onCerrar={() => setEditar(false)} onGuardar={async (datos: any) => {
        const r = await accion(() => api.patch(`/afore/clientes/${id}`, datos), "Datos actualizados.");
        if (r) { setEditar(false); setRevelado({}); if (r.revision?.curp && !r.revision.curp.valida_formato) setError(`CURP: ${r.revision.curp.detalle}`); }
      }} />}
    </AforeShell>
  );
}

function EditarCliente({ c, cat, onCerrar, onGuardar }: any) {
  const [f, setF] = useState<any>({ nombre: c.nombre, telefono: c.telefono || "", email: c.email || "", relacion: c.relacion, titular_estado: c.titular_estado,
    preferencia_contacto: c.preferencia_contacto, notas: c.notas || "", curp: "", nss: "" });
  const cambiar = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <Modal titulo="Editar datos del cliente" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault();
        const d: any = { ...f, telefono: f.telefono || null, email: f.email || null, notas: f.notas || null };
        if (!f.curp) delete d.curp; if (!f.nss) delete d.nss; onGuardar(d); }}>
        <label className="block sm:col-span-2"><span className="etiqueta">Nombre completo</span><input className="campo" required minLength={2} maxLength={200} value={f.nombre} onChange={cambiar("nombre")} /></label>
        <label className="block"><span className="etiqueta">Teléfono</span><input className="campo" value={f.telefono} onChange={cambiar("telefono")} /></label>
        <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" value={f.email} onChange={cambiar("email")} /></label>
        <label className="block"><span className="etiqueta">Nueva CURP (dejar vacío para conservar)</span><input className="campo font-mono uppercase" maxLength={18} autoComplete="off" value={f.curp} onChange={cambiar("curp")} /></label>
        <label className="block"><span className="etiqueta">Nuevo NSS (dejar vacío para conservar)</span><input className="campo font-mono" maxLength={11} autoComplete="off" value={f.nss} onChange={cambiar("nss")} /></label>
        <label className="block"><span className="etiqueta">Relación</span><select className="campo" value={f.relacion} onChange={cambiar("relacion")}>{Object.entries(cat.relaciones).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label className="block"><span className="etiqueta">Titular</span><select className="campo" value={f.titular_estado} onChange={cambiar("titular_estado")}>{Object.entries(cat.titular).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label className="block"><span className="etiqueta">Preferencia de contacto</span><select className="campo" value={f.preferencia_contacto} onChange={cambiar("preferencia_contacto")}>{Object.entries(cat.contacto).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label className="block sm:col-span-2"><span className="etiqueta">Notas internas</span><textarea className="campo" rows={2} maxLength={3000} value={f.notas} onChange={cambiar("notas")} /></label>
        <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Guardar</button></div>
      </form>
    </Modal>
  );
}
