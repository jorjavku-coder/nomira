"use client";
import { useEffect, useState } from "react";
import { Aviso, Modal } from "@/components/ui";

type Cliente = { get: (r: string) => Promise<any>; post: (r: string, c?: unknown) => Promise<any> };

/** Segundo paso del inicio de sesión: código de 6 dígitos de la app o un código de respaldo. */
export function PasoCodigo({ onEnviar, onCancelar, error, cargando }: { onEnviar: (codigo: string) => void; onCancelar: () => void; error: string; cargando: boolean }) {
  const [codigo, setCodigo] = useState("");
  const [respaldo, setRespaldo] = useState(false);
  return (
    <form onSubmit={(e) => { e.preventDefault(); onEnviar(codigo); }} className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-marino">Verificación en dos pasos</h2>
        <p className="mt-1 text-sm text-slate-500">{respaldo ? "Escriba uno de sus códigos de respaldo (cada uno sirve una sola vez)." : "Abra su app de autenticación y escriba el código de 6 dígitos de Nomira."}</p>
      </div>
      <label className="block"><span className="etiqueta">{respaldo ? "Código de respaldo" : "Código"}</span>
        <input className="campo text-center font-mono text-2xl tracking-[0.4em]" required autoFocus autoComplete="one-time-code"
          inputMode={respaldo ? "text" : "numeric"} maxLength={respaldo ? 9 : 6} placeholder={respaldo ? "xxxx-xxxx" : "000000"} value={codigo}
          onChange={(e) => setCodigo(respaldo ? e.target.value : e.target.value.replace(/\D/g, ""))} /></label>
      <Aviso>{error}</Aviso>
      <button className="btn-primario w-full py-2.5" disabled={cargando}>{cargando ? "Verificando…" : "Verificar y entrar"}</button>
      <div className="flex justify-between text-sm">
        <button type="button" className="font-medium text-turquesa-700 hover:underline" onClick={() => { setRespaldo(!respaldo); setCodigo(""); }}>{respaldo ? "Usar la app" : "No tengo mi celular"}</button>
        <button type="button" className="text-slate-500 hover:underline" onClick={onCancelar}>Volver</button>
      </div>
      {respaldo && <p className="text-xs text-slate-500">¿Tampoco tiene sus códigos de respaldo? Pida a un administrador de su despacho que le quite la verificación para volver a activarla.</p>}
    </form>
  );
}

/** Tarjeta para activar o desactivar la verificación en dos pasos (Mi perfil y panel de la plataforma). */
export function ConfigDosPasos({ api, ruta, onCerrarSesiones }: { api: Cliente; ruta: string; onCerrarSesiones?: () => Promise<void> }) {
  const [e, setE] = useState<any>(null);
  const [paso, setPaso] = useState<"contrasena" | "qr" | "codigos" | "quitar" | null>(null);
  const [contrasena, setContrasena] = useState("");
  const [codigo, setCodigo] = useState("");
  const [qr, setQr] = useState<any>(null);
  const [codigos, setCodigos] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  useEffect(() => { api.get(`${ruta}/dos-pasos`).then(setE).catch(() => {}); }, [api, ruta]);
  const cerrar = () => { setPaso(null); setContrasena(""); setCodigo(""); setError(""); };
  async function hacer(fn: () => Promise<any>) { setError(""); try { return await fn(); } catch (x: any) { setError(x.message); return null; } }
  if (!e) return null;
  return (
    <section className="tarjeta p-6">
      <h2 className="font-semibold text-marino">Verificación en dos pasos</h2>
      <p className="mt-1 text-sm text-slate-600">Además de su contraseña, al entrar se pide un código de 6 dígitos de una app en su celular (Google Authenticator, Microsoft Authenticator, 1Password…). Si alguien obtiene su contraseña, no podrá entrar sin su celular.</p>
      {e.activo ? <div className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900"><b>Activa.</b> Le quedan {e.respaldo_restantes} código(s) de respaldo.</div>
        : <div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><b>Desactivada.</b> Le recomendamos activarla: protege la información de sus clientes.</div>}
      <div className="mt-3 flex flex-wrap gap-2">
        {e.activo ? <>
          <button className="btn-sec" onClick={() => setPaso("quitar")}>Desactivar</button>
          <button className="btn-sec" onClick={() => { setCodigo(""); setPaso("codigos"); setCodigos([]); }}>Nuevos códigos de respaldo</button>
        </> : <button className="btn-turquesa" onClick={() => setPaso("contrasena")}>Activar verificación en dos pasos</button>}
        {onCerrarSesiones && <button className="btn-sec" onClick={async () => { setOk(""); if (await hacer(onCerrarSesiones) !== null) setOk("Se cerró su sesión en los demás navegadores y dispositivos."); }}>Cerrar sesión en los demás dispositivos</button>}
      </div>
      <div className="mt-3"><Aviso tipo="ok">{ok}</Aviso>{!paso && <Aviso>{error}</Aviso>}</div>

      {paso === "contrasena" && <Modal titulo="Activar verificación en dos pasos" onCerrar={cerrar}>
        <form className="space-y-3" onSubmit={async (ev) => { ev.preventDefault(); const r = await hacer(() => api.post(`${ruta}/dos-pasos/preparar`, { contrasena })); if (r) { setQr(r); setPaso("qr"); setCodigo(""); } }}>
          <p className="text-sm text-slate-600">Primero confirme su contraseña.</p>
          <input className="campo" type="password" required autoComplete="current-password" aria-label="Contraseña actual" value={contrasena} onChange={(x) => setContrasena(x.target.value)} />
          <Aviso>{error}</Aviso>
          <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={cerrar}>Cancelar</button><button className="btn-turquesa">Continuar</button></div>
        </form>
      </Modal>}

      {paso === "qr" && qr && <Modal titulo="Escanee el código con su app" onCerrar={cerrar}>
        <form className="space-y-3" onSubmit={async (ev) => { ev.preventDefault(); const r = await hacer(() => api.post(`${ruta}/dos-pasos/activar`, { codigo })); if (r) { setE(r); setCodigos(r.codigos_respaldo); setPaso("codigos"); } }}>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
            <li>Abra su app de autenticación y elija «Agregar cuenta» o «Escanear código QR».</li>
            <li>Escanee este código. Si no puede, escriba la clave que aparece debajo.</li>
            <li>Escriba el código de 6 dígitos que le muestra la app.</li>
          </ol>
          <div className="mx-auto w-56 rounded-xl bg-white p-2 ring-1 ring-crema-300" role="img" aria-label="Código QR para su app de autenticación" dangerouslySetInnerHTML={{ __html: qr.qr_svg }} />
          <p className="break-all text-center font-mono text-xs text-slate-600">{qr.secreto.replace(/(.{4})/g, "$1 ").trim()}</p>
          <input className="campo text-center font-mono text-xl tracking-[0.4em]" required inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="000000"
            aria-label="Código de 6 dígitos" value={codigo} onChange={(x) => setCodigo(x.target.value.replace(/\D/g, ""))} />
          <Aviso>{error}</Aviso>
          <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={cerrar}>Cancelar</button><button className="btn-turquesa" disabled={codigo.length !== 6}>Activar</button></div>
        </form>
      </Modal>}

      {paso === "codigos" && <Modal titulo="Códigos de respaldo" onCerrar={() => { if (codigos.length) setCodigos([]); cerrar(); }}>
        {codigos.length ? <div className="space-y-3 text-sm">
          <p>Guárdelos en un lugar seguro (por ejemplo, impresos o en su gestor de contraseñas). Cada uno sirve <b>una sola vez</b> si pierde su celular. <b>No se volverán a mostrar.</b></p>
          <ul className="grid grid-cols-2 gap-2 rounded-xl bg-crema/70 p-3 text-center font-mono text-base">{codigos.map((c) => <li key={c}>{c}</li>)}</ul>
          <div className="flex justify-end gap-2">
            <button className="btn-sec" onClick={() => navigator.clipboard?.writeText(codigos.join("\n"))}>Copiar</button>
            <button className="btn-turquesa" onClick={() => { setCodigos([]); cerrar(); }}>Ya los guardé</button></div>
        </div> : <form className="space-y-3" onSubmit={async (ev) => { ev.preventDefault(); const r = await hacer(() => api.post(`${ruta}/dos-pasos/respaldo`, { codigo })); if (r) { setE(r); setCodigos(r.codigos_respaldo); } }}>
          <p className="text-sm text-slate-600">Los códigos anteriores dejarán de servir. Escriba el código actual de su app.</p>
          <input className="campo text-center font-mono text-xl tracking-[0.4em]" required inputMode="numeric" maxLength={6} aria-label="Código de 6 dígitos" value={codigo} onChange={(x) => setCodigo(x.target.value.replace(/\D/g, ""))} />
          <Aviso>{error}</Aviso>
          <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={cerrar}>Cancelar</button><button className="btn-turquesa">Generar</button></div>
        </form>}
      </Modal>}

      {paso === "quitar" && <Modal titulo="Desactivar verificación en dos pasos" onCerrar={cerrar}>
        <form className="space-y-3" onSubmit={async (ev) => { ev.preventDefault(); const r = await hacer(() => api.post(`${ruta}/dos-pasos/desactivar`, { contrasena, codigo })); if (r) { setE(r); cerrar(); setOk("Verificación en dos pasos desactivada."); } }}>
          <p className="text-sm text-slate-600">Su cuenta quedará protegida solo con la contraseña.</p>
          <label className="block"><span className="etiqueta">Contraseña</span><input className="campo" type="password" required value={contrasena} onChange={(x) => setContrasena(x.target.value)} /></label>
          <label className="block"><span className="etiqueta">Código de la app o de respaldo</span><input className="campo font-mono" required value={codigo} onChange={(x) => setCodigo(x.target.value)} /></label>
          <Aviso>{error}</Aviso>
          <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={cerrar}>Cancelar</button><button className="btn-turquesa">Desactivar</button></div>
        </form>
      </Modal>}
    </section>
  );
}
