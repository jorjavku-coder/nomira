"use client";
import { useCallback, useEffect, useState } from "react";
import { AforeShell, recargarCatalogos } from "@/components/afore";
import { useSesion } from "@/components/Shell";
import { Aviso } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

export default function ConfiguracionAfore() {
  const sesion = useSesion();
  const admin = sesion?.usuario.rol === "administrador";
  const [cfg, setCfg] = useState<any>(null);
  const [f, setF] = useState({ phone_number_id: "", waba_id: "", numero: "", token: "" });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const cargar = useCallback(() => api.get("/afore/config").then(setCfg).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  if (!cfg) return <AforeShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AforeShell>;
  const w = cfg.whatsapp;
  return (
    <AforeShell>
      <h1 className="text-3xl font-extrabold text-marino">Configuración</h1>
      <div className="mt-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <section className="tarjeta space-y-3 p-5">
          <h2 className="font-semibold text-marino">WhatsApp Business Platform (API oficial de Meta)</h2>
          {w.conectado ? <Aviso tipo="ok">Conectado: número {w.numero || w.phone_number_id}{w.conectado_en && ` desde ${fechaHora(w.conectado_en)}`}. El token está {w.token}.</Aviso>
            : <Aviso tipo="alerta">No conectado. Mientras tanto, los mensajes por WhatsApp quedan como borradores; nunca se marcan como enviados.</Aviso>}
          {w.faltan_plataforma.length > 0 && <Aviso tipo="info">Para recibir confirmaciones de entrega y mensajes del cliente, el servidor de Nomira necesita: {w.faltan_plataforma.join("; ")}.</Aviso>}
          <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
            <li>En Meta Business, el despacho registra su número empresarial en WhatsApp Business Platform (Cloud API). No se usa WhatsApp Web ni códigos QR.</li>
            <li>Copie el <b>Phone number ID</b> y un <b>token de acceso</b> permanente de un usuario del sistema con permiso de mensajería.</li>
            <li>Configure el webhook de la app con la URL <code className="break-all rounded bg-crema px-1">{w.webhook}</code> y suscríbase a «messages».</li>
            <li>Cree y espere la aprobación de sus plantillas en Meta y registre sus nombres en «Catálogos y plantillas».</li>
          </ol>
          {admin && (
            <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); setError(""); setOk("");
              try { setCfg(await api.put("/afore/config/whatsapp", { ...f, waba_id: f.waba_id || null, numero: f.numero || null })); recargarCatalogos(); setF({ ...f, token: "" }); setOk("WhatsApp conectado. El token se guardó cifrado."); } catch (err: any) { setError(err.message); } }}>
              <div className="grid gap-2 sm:grid-cols-3">
                <input className="campo" required pattern="\d+" placeholder="Phone number ID" value={f.phone_number_id} onChange={(e) => setF({ ...f, phone_number_id: e.target.value })} />
                <input className="campo" placeholder="WhatsApp Business Account ID (opcional)" value={f.waba_id} onChange={(e) => setF({ ...f, waba_id: e.target.value })} />
                <input className="campo" placeholder="Número visible (opcional)" value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value })} />
              </div>
              <input className="campo" type="password" required minLength={20} autoComplete="off" placeholder="Token de acceso (no se volverá a mostrar)" value={f.token} onChange={(e) => setF({ ...f, token: e.target.value })} />
              <div className="flex gap-2"><button className="btn-primario">{w.conectado ? "Reemplazar conexión" : "Conectar"}</button>
                {w.conectado && <button type="button" className="btn-peligro" onClick={async () => { if (confirm("¿Desconectar WhatsApp? Los mensajes nuevos quedarán como borradores.")) { setCfg(await api.borrar("/afore/config/whatsapp")); setOk("WhatsApp desconectado."); } }}>Desconectar</button>}</div>
            </form>)}
        </section>
        <section className="space-y-5">
          <div className="tarjeta space-y-2 p-5">
            <h2 className="font-semibold text-marino">Aprobación humana de mensajes</h2>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              <li>Nomira prepara avisos operativos (documento solicitado, recepción confirmada, respuesta registrada, actualización del portal) solo si el cliente dio su consentimiento.</li>
              <li>Por omisión, todos quedan «Esperando aprobación». Los aprueba un administrador o el abogado responsable del caso.</li>
              <li>Si falta algo (consentimiento, teléfono, conexión o plantilla aprobada), quedan como borrador y se explica qué falta.</li>
              <li>En «Catálogos y plantillas» puede marcar una plantilla como automática; aun así solo sale si todo está listo.</li>
              <li>Los mensajes recibidos se asocian al cliente solo si hay certeza; si no, quedan «Por asignar». Nunca cambian el estado de un caso.</li>
            </ul>
          </div>
          <div className="tarjeta space-y-2 p-5">
            <h2 className="font-semibold text-marino">Validación oficial de CURP</h2>
            {cfg.curp_oficial.disponible ? <Aviso tipo="ok">Disponible.</Aviso> : <Aviso tipo="alerta">{cfg.curp_oficial.motivo}</Aviso>}
            <p className="text-sm text-slate-600">Se habilita cuando su despacho acredita su autorización ante Nomira y el servidor tiene las credenciales del servicio oficial. Mientras tanto se usa la revisión local de formato, que no es una consulta oficial. Las consultas se hacen solo dentro de un caso, con finalidad y consentimiento registrados.</p>
          </div>
        </section>
      </div>
    </AforeShell>
  );
}
