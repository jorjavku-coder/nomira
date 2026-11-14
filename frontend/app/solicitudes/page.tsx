"use client";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Aviso, Chip } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

export default function Solicitudes() {
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.get("/solicitudes").then(setLista).catch((e) => setError(e.estado === 404 ? "Esta sección es solo para quien opera la plataforma." : e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const marcar = (s: any) => {
    const atendida = s.estado !== "atendida";
    const nota = atendida ? prompt("Nota de seguimiento (opcional):", s.nota || "") : s.nota;
    if (atendida && nota === null) return;
    api.patch(`/solicitudes/${s.id}`, { estado: atendida ? "atendida" : "nueva", nota: nota || null }).then(cargar).catch((e) => setError(e.message));
  };
  const nuevas = (lista || []).filter((s) => s.estado === "nueva").length;
  return (
    <Shell>
      <h1 className="text-3xl font-extrabold text-marino">Solicitudes</h1>
      <p className="mb-6 mt-1 text-sm text-slate-500">Personas que pidieron informes o una suscripción desde la página de inicio.{lista && ` ${nuevas} sin atender.`}</p>
      <Aviso>{error}</Aviso>
      {lista && (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Interés</th><th>Contacto</th><th>Empresa</th><th>Expedientes/mes</th><th>Mensaje</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {lista.length === 0 && <tr><td colSpan={8} className="py-8 text-center text-slate-500">Aún no hay solicitudes.</td></tr>}
              {lista.map((s) => (
                <tr key={s.id} className={s.estado === "nueva" ? "bg-turquesa-50/40" : ""}>
                  <td className="whitespace-nowrap">{fechaHora(s.creado_en)}</td>
                  <td><span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${s.tipo === "suscripcion" ? "bg-turquesa-100 text-turquesa-700" : "bg-marino-50 text-marino"}`}>{s.tipo === "suscripcion" ? "Suscripción" : "Informes"}</span></td>
                  <td><div className="font-semibold">{s.nombre}</div><a className="text-turquesa-700 hover:underline" href={`mailto:${s.email}`}>{s.email}</a>{s.telefono && <div className="text-xs text-slate-500">{s.telefono}</div>}</td>
                  <td>{s.empresa || "—"}</td><td>{s.expedientes_mes || "—"}</td>
                  <td className="max-w-xs whitespace-pre-wrap text-slate-600">{s.mensaje || "—"}{s.nota && <div className="mt-1 text-xs italic text-slate-500">Nota: {s.nota}</div>}</td>
                  <td><Chip estado={s.estado === "atendida" ? "activo" : "pendiente"} texto={s.estado === "atendida" ? "Atendida" : "Nueva"} /></td>
                  <td className="text-right"><button className="btn-sec whitespace-nowrap" onClick={() => marcar(s)}>{s.estado === "atendida" ? "Reabrir" : "Marcar atendida"}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
