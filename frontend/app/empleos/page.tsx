"use client";
import { useEffect, useState } from "react";
import { CabeceraEmpleos, PieEmpleos, TarjetaVacante, pedirPublico } from "@/components/empleos";
import { Aviso } from "@/components/ui";

export default function Portal() {
  const [f, setF] = useState({ texto: "", area: "", modalidad: "", estado: "" });
  const [pagina, setPagina] = useState(1);
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const t = setTimeout(() => {
      const q = new URLSearchParams({ ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)), pagina: String(pagina) });
      pedirPublico(`/empleos?${q}`).then((x) => { setR(x); setError(""); }).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [f, pagina]);
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setPagina(1); setF({ ...f, [k]: e.target.value }); };
  const paginas = r ? Math.ceil(r.total / r.por_pagina) : 1;
  return (
    <>
      <CabeceraEmpleos />
      <main className="mx-auto max-w-5xl px-5 py-8">
        <h1 className="font-marca text-3xl font-extrabold text-marino sm:text-4xl">Bolsa de trabajo jurídica</h1>
        <p className="mt-1 text-slate-600">Vacantes de despachos y notarías que usan Nomira. Postúlate en línea con tu CV.</p>
        <form className="mt-5 grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]" role="search" onSubmit={(e) => e.preventDefault()}>
          <input className="campo" placeholder="Puesto, materia o ciudad" aria-label="Buscar" value={f.texto} onChange={pon("texto")} />
          <select className="campo" aria-label="Materia" value={f.area} onChange={pon("area")}><option value="">Todas las materias</option>
            {r && Object.entries(r.areas).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select>
          <select className="campo" aria-label="Modalidad" value={f.modalidad} onChange={pon("modalidad")}><option value="">Cualquier modalidad</option>
            {r && Object.entries(r.modalidades).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select>
          <select className="campo" aria-label="Estado" value={f.estado} onChange={pon("estado")}><option value="">Todo México</option>
            {r?.estados_mx.map((e: string) => <option key={e}>{e}</option>)}</select>
        </form>
        <div className="mt-4"><Aviso>{error}</Aviso></div>
        {r && <p className="mt-4 text-sm text-slate-500">{r.total === 1 ? "1 vacante" : `${r.total} vacantes`}</p>}
        <div className="mt-2 grid gap-3 sm:grid-cols-2">{r?.vacantes.map((v: any) => <TarjetaVacante key={v.codigo} v={v} />)}</div>
        {r && !r.total && <p className="tarjeta mt-2 p-6 text-center text-slate-600">No encontramos vacantes con esos filtros. Prueba con otros o vuelve pronto.</p>}
        {paginas > 1 && <div className="mt-5 flex justify-center gap-2">
          <button className="btn-sec" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
          <span className="self-center text-sm text-slate-600">Página {pagina} de {paginas}</span>
          <button className="btn-sec" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>Siguiente</button></div>}
        <section className="tarjeta mt-10 p-6 text-center">
          <h2 className="text-xl font-extrabold text-marino">¿Tienes un despacho y buscas personal?</h2>
          <p className="mt-1 text-slate-600">Publica tus vacantes gratis, recibe CVs ordenados y, si quieres, aplica pruebas psicométricas en línea.</p>
          <a href="/login?registro=1" className="btn-turquesa mt-3 inline-block">Crear cuenta gratis</a>
        </section>
      </main>
      <PieEmpleos />
    </>
  );
}
