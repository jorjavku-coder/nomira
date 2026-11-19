"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AforeShell, CampoDato, useCatalogos } from "@/components/afore";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

const PASOS = ["Cliente y titular", "Problema con la AFORE", "Instituciones y datos", "Revisión inicial"];
const vacio = { nombre: "", telefono: "", email: "", curp: "", nss: "", titular_estado: "vive", relacion: "titular", preferencia_contacto: "correo" };

/** Alta guiada en 4 pasos. Nada se completa automáticamente: solo lo que el despacho captura. */
export default function NuevoCaso() {
  const cat = useCatalogos();
  const router = useRouter();
  const [paso, setPaso] = useState(0);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [clientes, setClientes] = useState<any[]>([]);
  const [modoCliente, setModoCliente] = useState<"nuevo" | "existente">("nuevo");
  const [clienteId, setClienteId] = useState<string>("");
  const [c, setC] = useState<any>(vacio);
  const [consent, setConsent] = useState({ whatsapp: false, correo: false, medio: "verbal" });
  const [revision, setRevision] = useState<any>(null);
  const [caso, setCaso] = useState<any>({ tipo_problema: "", tipo_otro: "", titular_nombre: "", datos: {}, identificador_interno: "", responsable_id: "",
    siguiente_actividad: "", siguiente_fecha: "", restringido: false });
  const [solicitar, setSolicitar] = useState<string[]>([]);
  useEffect(() => { api.get("/afore/clientes").then(setClientes).catch(() => {}); }, []);
  useEffect(() => { const id = new URLSearchParams(window.location.search).get("cliente"); if (id) { setModoCliente("existente"); setClienteId(id); } }, []);
  const checklist: string[] = cat && caso.tipo_problema ? cat.checklists[caso.tipo_problema] || [] : [];
  useEffect(() => { setSolicitar(checklist); }, [caso.tipo_problema, cat]); // eslint-disable-line react-hooks/exhaustive-deps

  async function asegurarCliente(): Promise<number> {
    if (modoCliente === "existente") return Number(clienteId);
    if (clienteId) return Number(clienteId);
    const r = await api.post("/afore/clientes", { ...c, telefono: c.telefono || null, email: c.email || null, curp: c.curp || null, nss: c.nss || null });
    setRevision(r.revision);
    for (const canal of ["whatsapp", "correo"] as const) {
      if (consent[canal]) await api.post(`/afore/clientes/${r.id}/consentimientos`, { canal, medio: consent.medio });
    }
    setClienteId(String(r.id));
    return r.id;
  }
  async function siguiente() {
    setError("");
    try {
      if (paso === 0) {
        if (modoCliente === "existente" && !clienteId) throw new Error("Elija un cliente.");
        if (modoCliente === "nuevo" && c.nombre.trim().length < 2) throw new Error("Escriba el nombre completo.");
        setGuardando(true); await asegurarCliente();
      }
      if (paso === 1 && !caso.tipo_problema) throw new Error("Elija el problema.");
      setPaso(paso + 1);
    } catch (e: any) { setError(e.message); }
    setGuardando(false);
  }
  async function guardar(borrador: boolean) {
    setError(""); setGuardando(true);
    try {
      const cid = await asegurarCliente();
      const r = await api.post("/afore/casos", { ...caso, cliente_id: cid, borrador, responsable_id: caso.responsable_id ? Number(caso.responsable_id) : null,
        siguiente_fecha: caso.siguiente_fecha || null, tipo_otro: caso.tipo_otro || null, titular_nombre: caso.titular_nombre || null,
        identificador_interno: caso.identificador_interno || null, siguiente_actividad: caso.siguiente_actividad || null });
      if (!borrador && solicitar.length) {
        const d = await api.get(`/afore/casos/${r.id}`);
        for (const q of d.requisitos.filter((x: any) => solicitar.includes(x.nombre))) await api.patch(`/afore/requisitos/${q.id}`, { estado: "solicitado" });
      }
      router.push(`/afore/casos/${r.id}`);
    } catch (e: any) { setError(e.message); setGuardando(false); }
  }
  const cambiarC = (k: string) => (e: any) => setC({ ...c, [k]: e.target.value });
  const cambiarCaso = (k: string) => (e: any) => setCaso({ ...caso, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const dato = (k: string) => ({ valor: caso.datos[k], onCambio: (v: any) => setCaso({ ...caso, datos: { ...caso.datos, [k]: v } }) });
  if (!cat) return <AforeShell><p className="text-sm text-slate-500">Cargando…</p></AforeShell>;
  return (
    <AforeShell>
      <h1 className="text-3xl font-extrabold text-marino">Nuevo caso AFORE</h1>
      <ol className="my-5 grid gap-2 sm:grid-cols-4">
        {PASOS.map((t, i) => (
          <li key={t} className={`rounded-xl border px-3 py-2 text-sm ${i === paso ? "border-turquesa bg-turquesa-50 font-semibold text-marino" : i < paso ? "border-crema-300 text-slate-600" : "border-crema-300 text-slate-400"}`}>
            <span className="mr-1 font-marca font-bold">{i + 1}.</span>{t}{i < paso && " ✓"}</li>))}
      </ol>
      <div className="tarjeta space-y-4 p-5">
        {paso === 0 && (
          <>
            <div className="flex gap-2">
              <button type="button" className={modoCliente === "nuevo" ? "btn-primario" : "btn-sec"} onClick={() => { setModoCliente("nuevo"); setClienteId(""); }}>Cliente nuevo</button>
              <button type="button" className={modoCliente === "existente" ? "btn-primario" : "btn-sec"} onClick={() => setModoCliente("existente")} disabled={!clientes.length}>Cliente registrado</button>
            </div>
            {modoCliente === "existente" ? (
              <label className="block"><span className="etiqueta">Cliente</span>
                <select className="campo" value={clienteId} onChange={(e) => setClienteId(e.target.value)}>
                  <option value="">Elija…</option>{clientes.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
                </select></label>
            ) : (
              <>
                <p className="text-sm text-slate-500">Capture solo lo necesario para el caso. Puede dejar en blanco lo que aún no sepa.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block sm:col-span-2"><span className="etiqueta">Nombre completo de quien se comunica</span><input className="campo" maxLength={200} value={c.nombre} onChange={cambiarC("nombre")} autoFocus /></label>
                  <label className="block"><span className="etiqueta">Teléfono (10 dígitos)</span><input className="campo" inputMode="tel" maxLength={20} value={c.telefono} onChange={cambiarC("telefono")} /></label>
                  <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" maxLength={254} value={c.email} onChange={cambiarC("email")} /></label>
                  <label className="block"><span className="etiqueta">CURP (Clave Única de Registro de Población)</span><input className="campo font-mono uppercase" maxLength={18} autoComplete="off" value={c.curp} onChange={cambiarC("curp")} /></label>
                  <label className="block"><span className="etiqueta">NSS (Número de Seguridad Social del IMSS)</span><input className="campo font-mono" inputMode="numeric" maxLength={11} autoComplete="off" value={c.nss} onChange={cambiarC("nss")} /></label>
                  <label className="block"><span className="etiqueta">Quien se comunica es…</span>
                    <select className="campo" value={c.relacion} onChange={cambiarC("relacion")}>{Object.entries(cat.relaciones).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
                  <label className="block"><span className="etiqueta">La persona titular de la cuenta…</span>
                    <select className="campo" value={c.titular_estado} onChange={cambiarC("titular_estado")}>{Object.entries(cat.titular).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
                  <label className="block"><span className="etiqueta">Prefiere que lo contacten por</span>
                    <select className="campo" value={c.preferencia_contacto} onChange={cambiarC("preferencia_contacto")}>{Object.entries(cat.contacto).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
                </div>
                <p className="text-xs text-slate-500">CURP y NSS se guardan cifrados y se muestran enmascarados. La revisión de formato es local: no es una consulta oficial.</p>
                <fieldset className="rounded-xl border border-crema-300 p-3">
                  <legend className="etiqueta px-1">Consentimiento para recibir actualizaciones</legend>
                  <div className="flex flex-wrap gap-4 text-sm">
                    <label className="flex items-center gap-2"><input type="checkbox" checked={consent.whatsapp} disabled={!c.telefono} onChange={(e) => setConsent({ ...consent, whatsapp: e.target.checked })} /> Acepta recibirlas por WhatsApp</label>
                    <label className="flex items-center gap-2"><input type="checkbox" checked={consent.correo} disabled={!c.email} onChange={(e) => setConsent({ ...consent, correo: e.target.checked })} /> Acepta recibirlas por correo</label>
                    <label className="flex items-center gap-2">Cómo lo otorgó:
                      <select className="campo w-auto py-1" value={consent.medio} onChange={(e) => setConsent({ ...consent, medio: e.target.value })}>
                        <option value="verbal">De palabra</option><option value="escrito">Por escrito</option></select></label>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Se registra la fecha, el canal y el alcance («actualizaciones de su trámite»). El cliente puede revocarlo después.</p>
                </fieldset>
              </>
            )}
          </>
        )}
        {paso === 1 && (
          <>
            {revision?.curp && !revision.curp.valida_formato && <Aviso tipo="alerta">CURP: {revision.curp.detalle} Puede corregirla después en la ficha del cliente.</Aviso>}
            {revision?.nss && !revision.nss.valida_formato && <Aviso tipo="alerta">NSS: {revision.nss.detalle}</Aviso>}
            <p className="text-sm text-slate-600">¿Qué problema tiene con la AFORE?</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(cat.tipos).map(([k, t]: any) => (
                <label key={k} className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm ${caso.tipo_problema === k ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
                  <input type="radio" name="tipo" className="mt-0.5" checked={caso.tipo_problema === k} onChange={() => setCaso({ ...caso, tipo_problema: k })} /><span className="font-semibold text-marino">{t}</span>
                </label>))}
            </div>
            {caso.tipo_problema === "otro" && <label className="block"><span className="etiqueta">Describa el problema</span><input className="campo" maxLength={200} value={caso.tipo_otro} onChange={cambiarCaso("tipo_otro")} /></label>}
          </>
        )}
        {paso === 2 && (
          <>
            <p className="text-sm text-slate-500">Si no conoce un dato, elija «No lo sé», «Pendiente de confirmar» o «No aplica». Los montos son datos informados, no conclusiones.</p>
            <div className="grid gap-3 md:grid-cols-2">
              <CampoDato etiqueta="AFORE involucrada" lista={cat.afores} estados={cat.estados_dato} {...dato("afore")} />
              <CampoDato etiqueta="AFORE anterior (si aplica)" lista={cat.afores} estados={cat.estados_dato} {...dato("afore_anterior")} />
              <CampoDato etiqueta="AFORE receptora (si aplica)" lista={cat.afores} estados={cat.estados_dato} {...dato("afore_receptora")} />
              <CampoDato etiqueta="Institución relacionada (IMSS, ISSSTE…)" lista={cat.instituciones} estados={cat.estados_dato} {...dato("institucion")} />
              <CampoDato etiqueta="Régimen o tipo de resolución" estados={cat.estados_dato} {...dato("regimen")} />
              <CampoDato etiqueta="Monto que el cliente dice reclamar" monto estados={cat.estados_dato} {...dato("monto_cliente")} />
              <CampoDato etiqueta="Monto reportado por la AFORE" monto estados={cat.estados_dato} {...dato("monto_afore")} />
              <CampoDato etiqueta="Monto entregado" monto estados={cat.estados_dato} {...dato("monto_entregado")} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {c.titular_estado === "fallecio" || c.relacion !== "titular" ? (
                <label className="block"><span className="etiqueta">Nombre del titular de la cuenta</span><input className="campo" maxLength={200} value={caso.titular_nombre} onChange={cambiarCaso("titular_nombre")} /></label>) : null}
              <label className="block"><span className="etiqueta">Identificador interno del despacho</span><input className="campo" maxLength={80} value={caso.identificador_interno} onChange={cambiarCaso("identificador_interno")} /></label>
              <label className="block"><span className="etiqueta">Responsable del despacho</span>
                <select className="campo" value={caso.responsable_id} onChange={cambiarCaso("responsable_id")}><option value="">Sin asignar</option>
                  {cat.responsables.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
              <label className="block"><span className="etiqueta">Siguiente actividad</span><input className="campo" maxLength={300} placeholder="p. ej. Pedir estado de cuenta al cliente" value={caso.siguiente_actividad} onChange={cambiarCaso("siguiente_actividad")} /></label>
              <label className="block"><span className="etiqueta">Fecha de la siguiente actividad</span><input className="campo" type="date" value={caso.siguiente_fecha} onChange={cambiarCaso("siguiente_fecha")} /></label>
              <label className="flex items-start gap-2 rounded-xl border border-crema-300 p-3 text-sm sm:col-span-2"><input type="checkbox" className="mt-0.5" checked={caso.restringido} onChange={cambiarCaso("restringido")} />
                <span><b className="text-marino">Caso restringido</b><span className="block text-xs text-slate-500">Solo lo ven administradores, el responsable y quien lo creó.</span></span></label>
            </div>
            <p className="text-xs text-slate-500">Folios, solicitudes y respuestas se registran en la cronología del caso una vez creado.</p>
          </>
        )}
        {paso === 3 && (
          <>
            <Aviso tipo="info">Este checklist es una herramienta de organización para «{cat.tipos[caso.tipo_problema]}», no una lista definitiva de requisitos legales. Podrá editarlo en el caso.</Aviso>
            <p className="text-sm text-slate-600">Marque lo que quiere <b>pedir al cliente</b> desde ahora. Lo demás queda «No solicitado».</p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {checklist.map((x) => (
                <label key={x} className={`flex cursor-pointer items-center gap-2 rounded-xl border p-2.5 text-sm ${solicitar.includes(x) ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
                  <input type="checkbox" checked={solicitar.includes(x)} onChange={(e) => setSolicitar(e.target.checked ? [...solicitar, x] : solicitar.filter((y) => y !== x))} />{x}
                </label>))}
            </div>
          </>
        )}
        <Aviso>{error}</Aviso>
        <div className="flex flex-wrap justify-between gap-2 border-t border-crema-300 pt-4">
          <button className="btn-sec" disabled={paso === 0 || guardando} onClick={() => setPaso(paso - 1)}>← Atrás</button>
          <div className="flex flex-wrap gap-2">
            {paso >= 1 && <button className="btn-sec" disabled={guardando || !caso.tipo_problema} onClick={() => guardar(true)}>Guardar como borrador</button>}
            {paso < 3 ? <button className="btn-primario" disabled={guardando} onClick={siguiente}>{guardando ? "Guardando…" : "Siguiente →"}</button>
              : <button className="btn-turquesa" disabled={guardando} onClick={() => guardar(false)}>{guardando ? "Creando…" : "Abrir el caso"}</button>}
          </div>
        </div>
      </div>
    </AforeShell>
  );
}
