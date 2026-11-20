"use client";
import { useEffect, useState } from "react";
import { AcademiaShell, TarjetaCurso } from "@/components/academia";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

export default function Catalogo() {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [materia, setMateria] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => { api.get("/academia/cursos").then(setR).catch((e) => setError(e.message)); }, []);
  const t = q.trim().toLowerCase();
  const cursos = (r?.cursos || []).filter((c: any) => (!materia || c.materia === materia) && (!t || `${c.titulo} ${c.descripcion || ""} ${c.instructor || ""}`.toLowerCase().includes(t)));
  return (
    <AcademiaShell>
      <h1 className="text-3xl font-extrabold text-marino">Cursos</h1>
      <p className="mb-4 mt-1 text-sm text-slate-500">Cursos de su despacho y cursos prácticos de Nomira.</p>
      <div className="mb-4 flex flex-wrap gap-2">
        <select className="campo w-auto" value={materia} onChange={(e) => setMateria(e.target.value)} aria-label="Materia">
          <option value="">Todas las materias</option>{(r?.materias || []).map((x: string) => <option key={x}>{x}</option>)}</select>
        <input className="campo max-w-xs" placeholder="Buscar curso" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar curso" />
      </div>
      <Aviso>{error}</Aviso>
      {!r && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {r && cursos.length === 0 && <p className="tarjeta p-6 text-center text-sm text-slate-500">No hay cursos con esos filtros.</p>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{cursos.map((c: any) => <TarjetaCurso key={c.id} c={c} />)}</div>
    </AcademiaShell>
  );
}
