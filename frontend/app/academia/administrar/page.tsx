"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AcademiaShell, Barra, Ficha, Insignia, InsigniaAcceso } from "@/components/academia";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const COLOR: Record<string, string> = { borrador: "bg-amber-100 text-amber-800", publicado: "bg-emerald-100 text-emerald-800", archivado: "bg-slate-200 text-slate-600" };

export default function Administrar() {
  const router = useRouter();
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [importar, setImportar] = useState(false);
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
        <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => setImportar(true)} disabled={r && !r.limite.disponibles}>Importar o pedir ayuda</button>
          <button className="btn-turquesa" onClick={() => setNuevo(true)} disabled={r && !r.limite.disponibles}>+ Nuevo curso</button>
        </div>
      </div>
      <Aviso>{error}</Aviso>
      {r && <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <div className="tarjeta p-4">
          <div className="flex justify-between text-sm"><b className="text-marino">Cursos propios</b><span>{r.limite.usados} de {r.limite.limite}</span></div>
          <div className="mt-2"><Barra valor={r.limite.limite ? Math.round(100 * r.limite.usados / r.limite.limite) : 100} etiqueta="Cursos propios usados" /></div>
          <p className="mt-1 text-xs text-slate-500">{r.limite.incluidos} incluidos{r.limite.adicionales ? ` + ${r.limite.adicionales} adicionales` : ""}. Los cursos archivados no cuentan.</p>
          {!r.limite.disponibles && <p className="mt-2 text-sm text-amber-900">Llegó al límite de su plan. <Link className="font-semibold underline" href="/soporte">Contrate cursos adicionales con Nomira</Link> o archive un curso que ya no use.</p>}
        </div>
        <div className="tarjeta p-4">
          <div className="flex justify-between text-sm"><b className="text-marino">Espacio para videos y SCORM</b><span>{r.espacio.usado_mb} de {r.espacio.cuota_mb} MB</span></div>
          <div className="mt-2"><Barra valor={r.espacio.cuota_mb ? Math.min(100, Math.round(100 * r.espacio.usado_mb / r.espacio.cuota_mb)) : 100} etiqueta="Espacio usado" /></div>
          <p className="mt-1 text-xs text-slate-500">Videos de hasta {r.espacio.video_max_mb} MB. Los enlaces de YouTube o Vimeo no ocupan espacio.</p>
        </div>
      </div>}
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
                {c.entregado_por_nomira && <Insignia clase="ml-1 bg-turquesa-50 text-turquesa-700">Preparado por Nomira</Insignia>}
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
              <div className="min-w-0"><Link href={`/academia/cursos/${c.id}`} className="font-semibold text-marino hover:underline">{c.titulo}</Link>
                <span className="ml-2"><InsigniaAcceso c={c} /></span><Ficha c={c} /></div>
              <span className="text-xs text-slate-600">{c.iniciados} iniciaron · {c.completados} completaron</span>
              {c.acceso?.tipo === "pago" ? (!c.acceso.tiene_acceso && <Link className="btn-sec" href={`/academia/cursos/${c.id}`}>Ver precio</Link>)
                : <button className="btn-sec" onClick={() => duplicar(c.id)} disabled={!r.limite.disponibles}>Duplicar para adaptar</button>}
            </div>))}
        </div>
      </>}
      {nuevo && <NuevoCurso onCerrar={() => setNuevo(false)} onCreado={(id: number) => router.push(`/academia/administrar/${id}`)} />}
      {importar && <Importar onCerrar={() => setImportar(false)} onCreado={(id: number) => router.push(`/academia/administrar/${id}`)} />}
    </AcademiaShell>
  );
}

function NuevoCurso({ onCerrar, onCreado }: any) {
  const [d, setD] = useState<any>({ titulo: "", materia: "", modalidad: "autodirigido", juridico: false, asistido_ia: false, reconocimiento: "diploma" });
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
        <label className="block"><span className="etiqueta">Al terminar se entrega</span><select className="campo" value={d.reconocimiento} onChange={(e) => setD({ ...d, reconocimiento: e.target.value })}>
          <option value="diploma">Diploma</option><option value="constancia">Constancia de participación</option></select></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.juridico} onChange={(e) => setD({ ...d, juridico: e.target.checked })} />Tiene contenido jurídico (pedirá revisión antes de publicarse)</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={d.asistido_ia} onChange={(e) => setD({ ...d, asistido_ia: e.target.checked })} />Parte del material se preparó con ayuda de IA</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end"><button className="btn-turquesa">Crear y editar</button></div>
      </form>
    </Modal>
  );
}

const PESTANAS: [string, string][] = [["enlaces", "Pegar enlaces"], ["excel", "Plantilla de Excel"], ["scorm", "Archivo SCORM"], ["ayuda", "Pedir ayuda a Nomira"]];

/** Importar un curso: enlaces de video, plantilla de Excel, paquete SCORM, o pedir a Nomira que lo arme. */
function Importar({ onCerrar, onCreado }: { onCerrar: () => void; onCreado: (id: number) => void }) {
  const [tab, setTab] = useState("enlaces");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [f, setF] = useState({ titulo: "", materia: "", enlaces: "", descripcion: "", material: "" });
  const [archivo, setArchivo] = useState<File | null>(null);
  async function hacer(fn: () => Promise<any>) {
    setError(""); setOk(""); setOcupado(true);
    try { const r = await fn(); if (r?.id) onCreado(r.id); else if (r?.mensaje) setOk(r.mensaje); }
    catch (e: any) { setError(e.message); } finally { setOcupado(false); }
  }
  const subir = (ruta: string) => { const fd = new FormData(); fd.append("archivo", archivo!); return api.subir(ruta, fd); };
  return (
    <Modal titulo="Importar un curso" onCerrar={onCerrar} ancho="max-w-2xl">
      <div className="mb-4 flex flex-wrap gap-1 border-b border-crema-300" role="tablist">
        {PESTANAS.map(([k, t]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => { setTab(k); setArchivo(null); setError(""); setOk(""); }}
          className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold ${tab === k ? "border-turquesa text-marino" : "border-transparent text-slate-500"}`}>{t}</button>)}
      </div>
      {tab === "enlaces" && <div className="space-y-3">
        <p className="text-sm text-slate-600">Pegue los enlaces de sus videos de YouTube o Vimeo, uno por renglón. Se crea una lección por video con su título.</p>
        <label className="block"><span className="etiqueta">Enlaces</span><textarea className="campo font-mono text-xs" rows={6} value={f.enlaces} onChange={(e) => setF({ ...f, enlaces: e.target.value })}
          placeholder={"https://www.youtube.com/watch?v=...\nhttps://vimeo.com/..."} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Título del curso (opcional)</span><input className="campo" value={f.titulo} onChange={(e) => setF({ ...f, titulo: e.target.value })} /></label>
          <label><span className="etiqueta">Materia</span><input className="campo" value={f.materia} onChange={(e) => setF({ ...f, materia: e.target.value })} placeholder="Ej. Laboral" /></label>
        </div>
        <p className="text-xs text-slate-500">Las listas de reproducción no se pueden leer automáticamente: pegue el enlace de cada video.</p>
        <button className="btn-turquesa" disabled={!f.enlaces.trim() || ocupado} onClick={() => hacer(() => api.post("/academia/admin/importar/enlaces", { enlaces: f.enlaces, titulo: f.titulo || null, materia: f.materia || null }))}>{ocupado ? "Creando…" : "Crear curso"}</button>
      </div>}
      {tab === "excel" && <div className="space-y-3">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
          <li><button className="font-semibold text-turquesa-700 underline" onClick={() => api.descargar("/academia/admin/importar/plantilla", "plantilla-curso-nomira.xlsx").catch((e) => setError(e.message))}>Descargue la plantilla</button>.</li>
          <li>Llene el curso, una fila por lección y, si quiere, las preguntas del cuestionario.</li>
          <li>Súbala aquí. Si algo falta, le diremos en qué fila.</li>
        </ol>
        <input type="file" accept=".xlsx" aria-label="Plantilla llena" className="block text-sm" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
        <button className="btn-turquesa" disabled={!archivo || ocupado} onClick={() => hacer(() => subir("/academia/admin/importar/excel"))}>{ocupado ? "Importando…" : "Importar curso"}</button>
      </div>}
      {tab === "scorm" && <div className="space-y-3">
        <p className="text-sm text-slate-600">Suba el archivo ZIP de un curso SCORM (1.2 o 2004) exportado de otra plataforma. Se reproduce dentro de Nomira y guarda el avance y la calificación.</p>
        <input type="file" accept=".zip" aria-label="Paquete SCORM" className="block text-sm" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
        <p className="text-xs text-slate-500">Ocupa espacio de su despacho para videos y SCORM.</p>
        <button className="btn-turquesa" disabled={!archivo || ocupado} onClick={() => hacer(() => subir(`/academia/admin/importar/scorm${f.materia ? `?materia=${encodeURIComponent(f.materia)}` : ""}`))}>{ocupado ? "Subiendo… (puede tardar)" : "Importar SCORM"}</button>
      </div>}
      {tab === "ayuda" && <div className="space-y-3">
        <p className="text-sm text-slate-600">Cuéntenos qué curso necesita y comparta su material. Nomira lo prepara y se lo entrega como <b>borrador</b> para que lo revise y publique.</p>
        <label className="block"><span className="etiqueta">Tema o materia</span><input className="campo" value={f.materia} onChange={(e) => setF({ ...f, materia: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">¿Qué necesita?</span><textarea className="campo" rows={4} value={f.descripcion} onChange={(e) => setF({ ...f, descripcion: e.target.value })}
          placeholder="Ej. Un curso de inducción para recepción: cómo atender llamadas, qué datos pedir…" /></label>
        <label className="block"><span className="etiqueta">Material o enlaces (opcional)</span><textarea className="campo" rows={3} value={f.material} onChange={(e) => setF({ ...f, material: e.target.value })}
          placeholder="Enlaces a videos, presentaciones o documentos compartidos" /></label>
        <p className="text-xs text-slate-500">No incluya datos de clientes ni de expedientes.</p>
        <button className="btn-turquesa" disabled={f.materia.trim().length < 2 || f.descripcion.trim().length < 10 || ocupado}
          onClick={() => hacer(() => api.post("/academia/admin/ayuda", { materia: f.materia, descripcion: f.descripcion, enlaces: f.material || null }))}>Enviar solicitud a Nomira</button>
      </div>}
      <div className="mt-3"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
    </Modal>
  );
}
