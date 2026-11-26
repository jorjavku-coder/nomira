"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";

/** Página pública para que un comercio aliado compruebe la credencial de un miembro del Club Nomira. */
export default function Verificar() {
  const { codigo } = useParams<{ codigo: string }>();
  const [r, setR] = useState<any>(null);
  useEffect(() => {
    fetch(`/api/club-publico/verificar/${encodeURIComponent(codigo)}`).then((x) => x.json()).then(setR)
      .catch(() => setR({ valida: false, mensaje: "No pudimos comprobar la credencial. Intente de nuevo." }));
  }, [codigo]);
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-crema px-5">
      <Link href="/" aria-label="Nomira"><Logo /></Link>
      <div className="mt-6 w-full max-w-sm rounded-3xl bg-white p-6 text-center shadow-sm ring-1 ring-crema-300">
        <p className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Club Nomira · Verificación de credencial</p>
        {!r ? <p className="mt-6 text-slate-500">Comprobando…</p> : r.valida ? <>
          <p className="mt-4 text-5xl" aria-hidden>✅</p>
          <p className="mt-2 text-2xl font-extrabold text-emerald-700">Credencial vigente</p>
          <p className="mt-3 text-lg font-bold text-marino">{r.nombre}</p><p className="text-sm text-slate-600">{r.despacho}</p>
          <p className="mt-3 font-mono text-sm text-slate-500">{r.codigo}</p>
        </> : <>
          <p className="mt-4 text-5xl" aria-hidden>⚠️</p>
          <p className="mt-2 text-xl font-extrabold text-red-700">No válida</p><p className="mt-1 text-sm text-slate-600">{r.mensaje}</p></>}
      </div>
      <p className="mt-4 max-w-sm text-center text-xs text-slate-500">Esta página solo confirma si la persona es miembro vigente del Club Nomira. ¿Su empresa quiere ser aliada? <Link href="/aliados" className="font-semibold text-turquesa-700">Conozca cómo</Link>.</p>
    </div>
  );
}
