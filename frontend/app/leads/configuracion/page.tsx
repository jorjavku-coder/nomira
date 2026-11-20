"use client";
import { useEffect, useState } from "react";
import { Copiar, Etiqueta, LeadsShell, recargarCatalogosLeads, useCatalogosLeads } from "@/components/leads";
import { Aviso } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

export default function ConfiguracionLeads() {
  const cat = useCatalogosLeads();
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [clave, setClave] = useState<string | null>(null);
  const [listas, setListas] = useState<any>(null);
  const [wa, setWa] = useState<any>({ phone_number_id: "", numero: "", token: "", plantilla: "", plantilla_idioma: "es_MX" });
  const [mt, setMt] = useState<any>({ page_id: "", token: "" });
  const [avisoUrl, setAvisoUrl] = useState("");
  useEffect(() => { api.get("/leads/config").then((x) => { setC(x); setListas({ materias: x.materias.join("\n"), motivos: x.motivos_perdida.join("\n"), dias: x.dias_sin_actividad });
    setAvisoUrl(x.aviso_privacidad_url || "");
    setWa((w: any) => ({ ...w, phone_number_id: x.whatsapp.phone_number_id || "", numero: x.whatsapp.numero || "", plantilla: x.whatsapp.plantilla || "", plantilla_idioma: x.whatsapp.plantilla_idioma || "es_MX" })); })
    .catch((e) => setError(e.message)); }, []);
  async function hacer(fn: () => Promise<any>, exito: string) {
    setError(""); setOk("");
    try { const r = await fn(); if (r?.formulario) setC(r); setOk(exito); recargarCatalogosLeads(); return r; }
    catch (e: any) { setError(e.detalle?.faltantes ? `${e.message} Falta: ${e.detalle.faltantes.join("; ")}` : e.message); return null; }
  }
  if (!c || !cat) return <LeadsShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</LeadsShell>;
  const admin = cat.es_admin;
  const ejemplo = JSON.stringify({ nombre: "Nombre del prospecto", telefono: "5512345678", email: "correo@ejemplo.com", materia: "Laboral",
    descripcion: "Qué necesita", canal: "tiktok", campana: "CÓDIGO", consentimiento: true }, null, 2);
  return (
    <LeadsShell>
      <h1 className="mb-1 text-3xl font-extrabold text-marino">Configuración</h1>
      <p className="mb-4 text-sm text-slate-500">{admin ? "Ajuste listas y conecte sus fuentes de prospectos." : "Solo un administrador puede cambiar esta configuración."}</p>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="grid gap-5 xl:grid-cols-2">
        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Listas del despacho</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label><span className="etiqueta">Materias o servicios (uno por línea)</span>
              <textarea className="campo" rows={8} disabled={!admin} value={listas.materias} onChange={(e) => setListas({ ...listas, materias: e.target.value })} /></label>
            <label><span className="etiqueta">Motivos de «No contratado»</span>
              <textarea className="campo" rows={8} disabled={!admin} value={listas.motivos} onChange={(e) => setListas({ ...listas, motivos: e.target.value })} /></label>
            <label><span className="etiqueta">Avisar «sin actividad» después de (días)</span>
              <input className="campo" type="number" min={1} max={90} disabled={!admin} value={listas.dias} onChange={(e) => setListas({ ...listas, dias: e.target.value })} /></label>
          </div>
          {admin && <button className="btn-turquesa mt-3" onClick={() => hacer(() => api.patch("/leads/config", { materias: listas.materias.split("\n"), motivos_perdida: listas.motivos.split("\n"),
            dias_sin_actividad: Number(listas.dias) }), "Listas guardadas.")}>Guardar listas</button>}
        </section>

        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Aviso de privacidad del despacho</h2>
          <p className="mt-1 text-sm text-slate-600">Su despacho es el responsable de los datos que dejan sus prospectos y necesita su propio aviso de privacidad.
            El aviso de Nomira no lo sustituye. El enlace se mostrará junto a su formulario de contacto.</p>
          <div className="mt-2"><Etiqueta clase={c.aviso_privacidad_url ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>{c.aviso_privacidad_url ? "Enlace agregado" : "Falta el enlace"}</Etiqueta></div>
          <label className="mt-3 block"><span className="etiqueta">Dirección de su aviso de privacidad (https://…)</span>
            <input className="campo" type="url" inputMode="url" placeholder="https://www.sudespacho.mx/aviso-de-privacidad" disabled={!admin} maxLength={500}
              value={avisoUrl} onChange={(e) => setAvisoUrl(e.target.value)} /></label>
          {admin && <button className="btn-turquesa mt-3" onClick={() => hacer(() => api.patch("/leads/config", { aviso_privacidad_url: avisoUrl.trim() }),
            avisoUrl.trim() ? "Enlace del aviso guardado." : "Se quitó el enlace del aviso.")}>Guardar enlace</button>}
          <p className="mt-2 text-xs text-slate-500">¿Aún no tiene aviso? Consulte la guía y plantilla para despachos con su abogado. Nomira no redacta ni revisa el aviso de su despacho.</p>
        </section>

        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Formulario de contacto</h2>
          <p className="mt-1 text-sm text-slate-600">Página pública con el nombre de su despacho. Pide nombre, contacto, materia y una descripción breve, con autorización expresa. No pide documentos.</p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <Etiqueta clase={c.formulario.activo ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}>{c.formulario.activo ? "Activo" : "Apagado"}</Etiqueta>
            <code className="break-all rounded bg-crema-200 px-1.5 py-0.5 text-xs">{c.formulario.enlace}</code><Copiar texto={c.formulario.enlace} />
          </div>
          {admin && <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn-sec" onClick={() => hacer(() => api.patch("/leads/config", { formulario_activo: !c.formulario.activo }), c.formulario.activo ? "Formulario apagado." : "Formulario activado.")}>{c.formulario.activo ? "Apagar" : "Activar"}</button>
            <button className="btn-sec" onClick={() => hacer(() => api.post("/leads/config/formulario/renovar"), "Se generó un enlace nuevo; el anterior dejó de funcionar.")}>Generar enlace nuevo</button>
          </div>}
          <p className="mt-2 text-xs text-slate-500">Cada campaña tiene además su propio enlace (en «Campañas y fuentes»).</p>
        </section>

        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">WhatsApp Business Platform (API oficial de Meta)</h2>
          <div className="mt-2"><Etiqueta clase={c.whatsapp.conectado ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>{c.whatsapp.conectado ? `Conectado ${c.whatsapp.numero || ""}` : "No conectado"}</Etiqueta></div>
          {!c.whatsapp.conectado && <p className="mt-2 text-sm text-slate-600">Sin conexión puede seguir usando «Abrir en WhatsApp» desde cada prospecto y registrar la respuesta. No se usa WhatsApp Web, códigos QR ni envíos masivos.</p>}
          {c.whatsapp.faltan_plataforma.length > 0 && <div className="mt-2"><Aviso tipo="info">Para recibir mensajes y confirmaciones, el servidor de Nomira necesita: {c.whatsapp.faltan_plataforma.join("; ")}.</Aviso></div>}
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-600">
            <li>Registre su número empresarial en WhatsApp Business Platform (Cloud API) desde Meta Business.</li>
            <li>Copie el <b>Phone number ID</b> y un <b>token de acceso</b> permanente con permiso de mensajería.</li>
            <li>En la app de Meta, configure el webhook <code className="break-all">{c.whatsapp.webhook}</code> y suscríbase a «messages».</li>
            <li>Opcional: registre una plantilla aprobada para escribir a quien no le ha escrito en las últimas 24 h (Meta lo exige). Use una sola variable: el nombre.</li>
          </ol>
          {admin && <form className="mt-3 grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); hacer(() => api.put("/leads/config/whatsapp", { ...wa, token: wa.token || null, plantilla: wa.plantilla || null, numero: wa.numero || null }), "WhatsApp conectado.").then((r) => r && setWa({ ...wa, token: "" })); }}>
            <input className="campo" required placeholder="Phone number ID" value={wa.phone_number_id} onChange={(e) => setWa({ ...wa, phone_number_id: e.target.value.trim() })} />
            <input className="campo" placeholder="Número visible (+52…)" value={wa.numero} onChange={(e) => setWa({ ...wa, numero: e.target.value })} />
            <input className="campo sm:col-span-2" type="password" autoComplete="off" placeholder={c.whatsapp.conectado ? "Token guardado (déjelo vacío para conservarlo)" : "Token de acceso (no se volverá a mostrar)"} value={wa.token} onChange={(e) => setWa({ ...wa, token: e.target.value })} />
            <input className="campo" placeholder="Plantilla aprobada (opcional, p. ej. primer_contacto)" value={wa.plantilla} onChange={(e) => setWa({ ...wa, plantilla: e.target.value.trim() })} />
            <input className="campo" placeholder="Idioma de la plantilla" value={wa.plantilla_idioma} onChange={(e) => setWa({ ...wa, plantilla_idioma: e.target.value.trim() })} />
            <div className="flex gap-2 sm:col-span-2"><button className="btn-primario">{c.whatsapp.conectado ? "Guardar cambios" : "Conectar"}</button>
              {c.whatsapp.conectado && <button type="button" className="btn-peligro" onClick={() => hacer(() => api.borrar("/leads/config/whatsapp"), "WhatsApp desconectado.")}>Desconectar</button>}</div>
          </form>}
          {c.whatsapp.conectado_en && <p className="mt-2 text-xs text-slate-500">Conectado el {fechaHora(c.whatsapp.conectado_en)}.</p>}
        </section>

        <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Anuncios de Facebook e Instagram (formularios de clientes potenciales)</h2>
          <div className="mt-2"><Etiqueta clase={c.meta.conectado ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>{c.meta.conectado ? `Conectado${c.meta.pagina ? ` · ${c.meta.pagina}` : ""}` : "No conectado"}</Etiqueta></div>
          {c.meta.faltan_plataforma.length > 0 && <div className="mt-2"><Aviso tipo="info">Para conectar anuncios, el servidor de Nomira necesita: {c.meta.faltan_plataforma.join("; ")}.</Aviso></div>}
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-600">
            <li>En la app de Meta de Nomira se registra el webhook <code className="break-all">{c.meta.webhook}</code> (objeto «Page», campo «leadgen»).</li>
            <li>Copie el <b>ID de su página</b> de Facebook y un <b>token de acceso de la página</b> con permisos de formularios (leads_retrieval).</li>
            <li>Al conectar, Nomira suscribe su página. Cada formulario enviado llega como prospecto con su campaña de Meta.</li>
          </ol>
          {admin && (c.meta.conectado
            ? <button className="btn-peligro mt-3" onClick={() => hacer(() => api.borrar("/leads/config/meta"), "Anuncios desconectados.")}>Desconectar</button>
            : <form className="mt-3 grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); hacer(() => api.put("/leads/config/meta", mt), "Página conectada.").then((r) => r && setMt({ page_id: "", token: "" })); }}>
              <input className="campo" required placeholder="ID de la página" value={mt.page_id} onChange={(e) => setMt({ ...mt, page_id: e.target.value.trim() })} />
              <input className="campo" required type="password" autoComplete="off" placeholder="Token de la página" value={mt.token} onChange={(e) => setMt({ ...mt, token: e.target.value })} />
              <button className="btn-primario sm:col-span-2 sm:justify-self-start">Conectar página</button>
            </form>)}
        </section>

        <section className="tarjeta p-5 xl:col-span-2">
          <h2 className="font-semibold text-marino">Otros sistemas: Google Ads, TikTok, Mailchimp, Zapier, Make o su sitio web</h2>
          <p className="mt-1 text-sm text-slate-600">Envían prospectos a Nomira con una clave secreta. Nomira solo guarda su huella: si la pierde, genere otra.</p>
          <div className="mt-2 flex flex-wrap items-center gap-2"><Etiqueta clase={c.entrada.configurada ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}>{c.entrada.configurada ? `Clave activa (termina en ${c.entrada.pista})` : "Sin clave"}</Etiqueta></div>
          {clave && <div className="mt-3"><Aviso tipo="alerta">Copie esta clave ahora: no se volverá a mostrar. <code className="break-all font-mono">{clave}</code> <Copiar texto={clave} /></Aviso></div>}
          {admin && <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn-primario" onClick={() => hacer(() => api.post("/leads/config/entrada"), "Clave generada.").then((r) => r && setClave(r.clave))}>{c.entrada.configurada ? "Generar clave nueva" : "Generar clave"}</button>
            {c.entrada.configurada && <button className="btn-peligro" onClick={() => hacer(() => api.borrar("/leads/config/entrada"), "Clave revocada.").then(() => setClave(null))}>Revocar clave</button>}
          </div>}
          <div className="mt-3 grid gap-3 text-xs text-slate-600 lg:grid-cols-2">
            <div><p><b>Zapier, Make o su sitio:</b> envíe un POST a</p>
              <p className="mt-1 flex flex-wrap items-center gap-2"><code className="break-all rounded bg-crema-200 px-1.5 py-0.5">{c.entrada.url}</code><Copiar texto={c.entrada.url} /></p>
              <p className="mt-1">con el encabezado <code>X-Nomira-Clave: su clave</code> y un cuerpo JSON como:</p>
              <pre className="mt-1 overflow-x-auto rounded-xl bg-marino-900 p-3 text-[11px] text-white">{ejemplo}</pre>
              <p className="mt-1">«campana» acepta el código o el nombre exacto de la campaña. Sin «consentimiento: true» no se registra autorización de contacto.</p></div>
            <div><p><b>Formularios de Google Ads:</b> en «Integración de webhook» del formulario, pegue la misma URL y use su clave como «Clave» (google_key). Las pruebas de Google se reconocen y no crean prospectos.</p>
              <p className="mt-2"><b>TikTok, LinkedIn o Mailchimp:</b> conéctelos con Zapier o Make usando la URL y la clave. Indique «canal» (p. ej. <code>tiktok</code>) para atribuirlos.</p></div>
          </div>
        </section>
      </div>
    </LeadsShell>
  );
}
