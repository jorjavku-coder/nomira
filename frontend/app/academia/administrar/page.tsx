"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AcademiaShell, Ficha, Insignia } from "@/components/academia";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const COLOR: Record<string, string> = { borrador: "bg-amber-100 text-amber-800", publicado: "bg-emerald-100 text-emerald-800", archivado: "bg-slate-200 text-slate-600" };

export default function Administrar() {
  const router = useRouter();
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  useEffect(() => { api.get("/academia/admin/cursos").then(setR).catch((e) => setError(e.message)); }, []);
  const propios = r?.cursos.filter((c: any) => c.origen === "despacho") || [];
  const nomira = r?.cursos.filter((c: any) => c.origen === "nomira") || [];
  async function duplicar(id: number) {
    try { const c = await api.post(`/academia/admin/cursos/${id}/duplicar`); router.push(`/academia/administrar/${c.id}`); } catch (e: any) { setError(e.message); }
  }
  return (
    <AcademiaShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Administrar cursos</h1>
          <p className="text-sm text-slate-500">Cree cursos internos, actualícelos o archívelos. El avance de quien ya los tomó nunca se borra.</p></div>
        <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo curso</button>
      </div>
      <Aviso>{error}</Aviso>
      {!r && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {r && <>
        <h2 className="mb-2 mt-2 text-lg font-bold text-marino">Cursos de su despacho</h2>
        {propios.length === 0 && <p className="tarjeta p-5 text-sm text-slate-500">Aún no tiene cursos propios. Cree uno (por ejemplo «Atención inicial en nuestro despacho» o «Proceso interno ISSSTE») o duplique un curso de Nomira para adaptarlo.</p>}
        <div className="tarjeta divide-y divide-crema-200">
          {propios.map((c: any) => (
            <div key={c.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <Link href={`/academia/administrar/${c.id}`} className="font-semibold text-marino hover:underline">{c.titulo}</Link>
                <Insignia clase={`ml-2 ${COLOR[c.estado]}`}>{c.estado_texto}</Insignia>
                {c.aviso_vigencia && <Insignia clase="ml-1 bg-amber-100 text-amber-800">Revisar vigencia</Insignia>}
                <Ficha c={c} />
              </div>
              <span className="text-xs text-slate-600">{c.lecciones} lección(es) · {c.asignaciones} asignación(es) · {c.iniciados} iniciaron · {c.completados} completaron</span>
              {c.editable && <Link className="btn-sec" href={`/academia/administrar/${c.id}`}>Editar</Link>}
            </div>))}
        </div>
        <h2 className="mb-2 mt-8 text-lg font-bold text-marino">Cursos de Nomira</h2>
        <p className="mb-2 text-sm text-slate-500">Prácticos y operativos. No se editan, pero puede asignarlos o duplicarlos para adaptarlos a su despacho.</p>
        <div className="tarjeta divide-y divide-crema-200">
          {nomira.map((c: any) => (
            <div key={c.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="min-w-0"><Link href={`/academia/cursos/${c.id}`} className="font-semibold text-marino hover:underline">{c.titulo}</Link><Ficha c={c} /></div>
              <span className="text-xs text-slate-600">{c.iniciados} iniciaron · {c.completados} completaron</span>
              <button className="btn-sec" onClick={() => duplicar(c.id)}>Duplicar para adaptar</button>
            </div>))}
        </div>
      </>}
      {nuevo && <NuevoCurso onCerrar={() => setNuevo(false)} onCreado={(id: number) => router.push(`/academia/administrar/${id}`)} />}
    </AcademiaShell>
  );
}

function NuevoCurso({ onCerrar, onCreado }: any) {
  const [d, setD] = useState<any>({ titulo: "", materia: "", modalidad: "autodirigido", juridico: false, asistido_ia: false });
  const [error, setError] = useState("");
  return (
    <Modal titulo="Nuevo curso" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault(); setError("");
        try { const c = await api.post("/academia/admin/cursos", d); onCreado(c.id); } catch (x: any) { setError(x.message); }
      }}>
        <label className="block"><span className="etiqueta">Título</span><input className="campo" required minLength={3} autoFocus value={d.titulo} onChange={(e) => setD({ ...d, titulo: e.target.value })} placeholder="Ej. Seguimiento de trámites ISSEMYM" /></label>
        <label className="block"><span className="etiqueta">Materia</span><input className="campo" required minLength={2} value={d.materia} onChange={(e) => setD({ ...d, materia: e.target.value })} placeholder="Ej. ISSEMYM, AFORE, Procesos internos" /></label>
        <label className="block"><span className="etiqueta">Modalidad</span><select className="campo" value={d.modalidad} onChange={(e) => setD({ ...d, modalidad: e.target.value })}>
          <option value="autodirigido">Autodirigido</option><option value="en_vivo">En vivo</option><option value="combinado">Combinado</option></select></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.juridico} onChange={(e) => setD({ ...d, juridico: e.target.checked })} />Tiene contenido jurídico (pedirá revisión antes de publicarse)</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.asistido_ia} onChange={(e) => setD({ ...d, asistido_ia: e.target.checked })} />Parte del material se preparó con ayuda de IA</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end"><button className="btn-turquesa">Crear y editar</button></div>
      </form>
    </Modal>
  );
}
