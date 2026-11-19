"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AforeShell, Pastilla } from "@/components/afore";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

export default function ClientesAfore() {
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { const t = setTimeout(() => api.get(`/afore/clientes${q ? `?q=${encodeURIComponent(q)}` : ""}`).then(setLista).catch((e) => setError(e.message)), 250); return () => clearTimeout(t); }, [q]);
  return (
    <AforeShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold text-marino">Clientes</h1>
        <Link href="/afore/casos/nuevo" className="btn-turquesa">+ Nuevo caso y cliente</Link>
      </div>
      <input className="campo mb-4 max-w-md" placeholder="Buscar por nombre" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar cliente" />
      <Aviso>{error}</Aviso>
      {!lista ? <p className="text-sm text-slate-500">Cargando…</p> : lista.length === 0 ? <div className="tarjeta p-10 text-center text-sm text-slate-500">Sin clientes.</div> : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Nombre</th><th>Relación</th><th>Contacto</th><th>CURP / NSS</th><th>Actualizaciones</th><th>Casos</th></tr></thead>
            <tbody>{lista.map((c) => (
              <tr key={c.id}>
                <td><Link className="font-semibold text-marino hover:underline" href={`/afore/clientes/${c.id}`}>{c.nombre}</Link></td>
                <td className="text-sm">{c.relacion_texto}{c.titular_estado === "fallecio" && <div className="text-xs text-slate-500">Titular fallecido</div>}</td>
                <td className="text-sm">{c.telefono_mascara || "—"}<div className="text-xs text-slate-500">{c.email || ""}</div></td>
                <td className="font-mono text-xs">{c.curp || "—"}<div>{c.nss || ""}</div></td>
                <td className="space-x-1">{c.consiente.whatsapp && <Pastilla clase="bg-emerald-50 text-emerald-800">WhatsApp</Pastilla>}{c.consiente.correo && <Pastilla clase="bg-sky-50 text-sky-800">Correo</Pastilla>}
                  {!c.consiente.whatsapp && !c.consiente.correo && <span className="text-xs text-slate-400">Sin consentimiento</span>}</td>
                <td>{c.casos}</td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </AforeShell>
  );
}
