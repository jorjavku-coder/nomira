"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Copiar, Etiqueta, LeadsShell, recargarCatalogosLeads, useCatalogosLeads } from "@/components/leads";
import { Aviso, Modal } from "@/components/ui";
import { api, fecha, mxn } from "@/lib/api";

/** Cómo conectar una campaña según su canal: siempre con medios oficiales y sin fingir integraciones. */
function Instrucciones({ c }: { c: any }) {
  const conUtm = `${c.enlace_formulario.split("#")[0]}?${c.utm}#${c.enlace_formulario.split("#")[1]}`;
  const redes = ["facebook", "instagram", "tiktok", "linkedin", "google"].includes(c.canal);
  return (
    <div className="space-y-2 text-xs text-slate-600">
      {c.canal === "whatsapp" && (c.enlace_whatsapp
        ? <p><b>WhatsApp:</b> comparta este enlace (estados, anuncios «clic a WhatsApp», tarjetas). El mensaje ya incluye el código <b>{c.codigo}</b> y Nomira lo atribuye a esta campaña al recibirlo.
            <span className="mt-1 flex flex-wrap items-center gap-2"><code className="break-all rounded bg-crema-200 px-1.5 py-0.5">{c.enlace_whatsapp}</code><Copiar texto={c.enlace_whatsapp} /></span></p>
        : <p><b>WhatsApp:</b> para un enlace que abra su WhatsApp con el código de la campaña, registre su número en <Link className="font-semibold text-turquesa-700 underline" href="/leads/configuracion">Configuración</Link>. Mientras tanto, use el formulario.</p>)}
      {c.canal === "correo" && <p><b>Correo:</b> pegue el enlace del formulario como botón «Quiero que me contacten» en su boletín o correo masivo (desde su herramienta de correo). Nomira no envía correos masivos.</p>}
      {redes && <p><b>Redes y anuncios:</b> use el enlace con parámetros como destino del anuncio o en la biografía. Si usa formularios de anuncios de Facebook/Instagram, conéctelos en Configuración y ponga aquí el ID de la campaña de Meta para atribuirlos.</p>}
      <p className="flex flex-wrap items-center gap-2"><b>Enlace del formulario:</b> <code className="break-all rounded bg-crema-200 px-1.5 py-0.5">{conUtm}</code><Copiar texto={conUtm} /></p>
    </div>
  );
}

export default function Campanas() {
  const cat = useCatalogosLeads();
  const [r, setR] = useState<any>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [editar, setEditar] = useState<any>(null);
  const cargar = () => api.get("/leads/campanas").then(setR).catch((e) => setError(e.message));
  useEffect(() => { cargar(); api.get("/leads/config").then(setCfg).catch(() => {}); }, []);
  const admin = cat?.es_admin;
  return (
    <LeadsShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Campañas y fuentes</h1>
          <p className="text-sm text-slate-500">De dónde llegan sus prospectos: WhatsApp, correo, redes sociales, su sitio web o recomendaciones.</p></div>
        {admin && <button className="btn-turquesa" onClick={() => setEditar({})}>+ Nueva campaña</button>}
      </div>
      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      {cfg && (
        <section className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Fuente titulo="Formulario de contacto" estado={cfg.formulario.activo ? "Activo" : "Apagado"} ok={cfg.formulario.activo}
            texto="Para su sitio web, firma de correo o biografía de redes. Quien lo llena aparece en la bandeja con su autorización.">
            {cfg.formulario.activo && <span className="flex flex-wrap items-center gap-2"><Copiar texto={cfg.formulario.enlace} etiqueta="Copiar enlace" />
              <a className="text-xs font-semibold text-turquesa-700 underline" href={cfg.formulario.enlace} target="_blank" rel="noopener noreferrer">Ver</a></span>}
          </Fuente>
          <Fuente titulo="WhatsApp Business Platform" estado={cfg.whatsapp.conectado ? "Conectado" : "No conectado"} ok={cfg.whatsapp.conectado}
            texto={cfg.whatsapp.conectado ? "Los mensajes a su número llegan como prospectos y se vinculan a su conversación." : "Sin conexión: puede abrir WhatsApp con un mensaje listo y registrar la respuesta."} />
          <Fuente titulo="Anuncios de Facebook e Instagram" estado={cfg.meta.conectado ? `Conectado${cfg.meta.pagina ? ` · ${cfg.meta.pagina}` : ""}` : "No conectado"} ok={cfg.meta.conectado}
            texto="Los formularios de sus anuncios llegan solos, con la campaña de Meta de donde vinieron." />
          <Fuente titulo="Otros sistemas" estado={cfg.entrada.configurada ? "Clave activa" : "Sin clave"} ok={cfg.entrada.configurada}
            texto="Google Ads (formularios), TikTok, Mailchimp o su sitio web por Zapier o Make." />
          <p className="text-xs text-slate-500 md:col-span-2 xl:col-span-4">Para conectar o desconectar, vaya a <Link className="font-semibold text-turquesa-700 underline" href="/leads/configuracion">Configuración</Link>. Nomira no publica anuncios ni envía mensajes masivos.</p>
        </section>)}

      {!r && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {r?.campanas.length === 0 && (
        <section className="tarjeta p-6 text-sm text-slate-600">
          <h2 className="text-lg font-bold text-marino">Aún no hay campañas</h2>
          <p className="mt-1">Cree una por cada anuncio, publicación, boletín o evento que quiera medir. Nomira le da un enlace y un código para saber cuántos prospectos y clientes trajo.</p>
        </section>)}
      <div className="space-y-4">
        {r?.campanas.map((c: any) => (
          <article key={c.id} className={`tarjeta p-5 ${c.activa ? "" : "opacity-70"}`}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-lg font-bold text-marino">{c.nombre} {!c.activa && <Etiqueta>Terminada</Etiqueta>}</h2>
                <p className="text-xs text-slate-500">{c.canal_texto} · Código {c.codigo}{c.inicio ? ` · desde ${fecha(c.inicio)}` : ""}{c.fin ? ` hasta ${fecha(c.fin)}` : ""}{c.id_externo ? ` · ID externo ${c.id_externo}` : ""}</p>
              </div>
              {admin && <button className="btn-sec text-xs" onClick={() => setEditar(c)}>Editar</button>}
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-center text-sm sm:grid-cols-5">
              {[["Prospectos", c.recibidos ?? 0], ["Consultas", c.consultas_realizadas ?? 0], ["Contratados", c.contratados ?? 0],
                ["Inversión", c.inversion ? mxn(c.inversion) : "—"], ["Costo por cliente", c.costo_por_cliente ? mxn(c.costo_por_cliente) : "—"]].map(([t, v]) => (
                <div key={t as string} className="rounded-xl bg-crema/60 px-2 py-2"><dt className="text-[11px] uppercase tracking-wide text-slate-500">{t}</dt><dd className="font-bold text-marino">{v}</dd></div>))}
            </dl>
            {c.activa && <div className="mt-3"><Instrucciones c={c} /></div>}
            {c.recibidos > 0 && <Link className="mt-2 inline-block text-xs font-semibold text-turquesa-700 underline" href={`/leads/prospectos?vista=todos&campana=${c.id}`}>Ver prospectos</Link>}
          </article>))}
      </div>
      {editar && <EditarCampana c={editar} cat={cat} onCerrar={() => setEditar(null)} onGuardado={(m: string) => { setEditar(null); setOk(m); cargar(); recargarCatalogosLeads(); }} />}
    </LeadsShell>
  );
}

function Fuente({ titulo, estado, ok, texto, children }: any) {
  return (
    <div className="tarjeta p-4 text-sm">
      <p className="font-semibold text-marino">{titulo}</p>
      <Etiqueta clase={ok ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}>{estado}</Etiqueta>
      <p className="mt-2 text-xs text-slate-500">{texto}</p>
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}

function EditarCampana({ c, cat, onCerrar, onGuardado }: any) {
  const nueva = !c.id;
  const [d, setD] = useState<any>({ nombre: c.nombre || "", canal: c.canal || "facebook", inversion: c.inversion || "", inicio: c.inicio || "", fin: c.fin || "",
    notas: c.notas || "", id_externo: c.id_externo || "", activa: c.activa ?? true });
  const [error, setError] = useState("");
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    const cuerpo = { ...d, inversion: d.inversion || null, inicio: d.inicio || null, fin: d.fin || null, notas: d.notas || null, id_externo: d.id_externo || null };
    try {
      if (nueva) await api.post("/leads/campanas", cuerpo); else await api.patch(`/leads/campanas/${c.id}`, cuerpo);
      onGuardado(nueva ? "Campaña creada: copie su enlace y úselo en su anuncio, correo o publicación." : "Campaña actualizada.");
    } catch (x: any) { setError(x.message); }
  }
  return (
    <Modal titulo={nueva ? "Nueva campaña" : "Editar campaña"} onCerrar={onCerrar}>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={guardar}>
        <label className="sm:col-span-2"><span className="etiqueta">Nombre</span><input className="campo" required minLength={2} value={d.nombre} onChange={(e) => setD({ ...d, nombre: e.target.value })} placeholder="Ej. Facebook — despidos (noviembre)" /></label>
        <label><span className="etiqueta">Canal</span><select className="campo" value={d.canal} onChange={(e) => setD({ ...d, canal: e.target.value })}>
          {Object.entries(cat?.canales || {}).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label><span className="etiqueta">Inversión (opcional)</span><input className="campo" inputMode="decimal" value={d.inversion} onChange={(e) => setD({ ...d, inversion: e.target.value })} placeholder="0.00" /></label>
        <label><span className="etiqueta">Inicio</span><input className="campo" type="date" value={d.inicio} onChange={(e) => setD({ ...d, inicio: e.target.value })} /></label>
        <label><span className="etiqueta">Fin</span><input className="campo" type="date" value={d.fin} onChange={(e) => setD({ ...d, fin: e.target.value })} /></label>
        <label className="sm:col-span-2"><span className="etiqueta">ID de la campaña en Meta o Google (opcional)</span><input className="campo" value={d.id_externo} onChange={(e) => setD({ ...d, id_externo: e.target.value })} /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Notas</span><input className="campo" maxLength={500} value={d.notas} onChange={(e) => setD({ ...d, notas: e.target.value })} /></label>
        {!nueva && <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.activa} onChange={(e) => setD({ ...d, activa: e.target.checked })} />Campaña activa (si la termina, su enlace deja de recibir prospectos)</label>}
        <p className="text-xs text-slate-500 sm:col-span-2">La inversión solo se usa para calcular el costo por cliente en sus reportes.</p>
        <div className="sm:col-span-2"><Aviso>{error}</Aviso></div>
        <div className="flex justify-end sm:col-span-2"><button className="btn-turquesa">{nueva ? "Crear campaña" : "Guardar"}</button></div>
      </form>
    </Modal>
  );
}
