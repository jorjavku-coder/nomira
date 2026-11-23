"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Aviso } from "@/components/ui";
import { api, mxn } from "@/lib/api";

/** Recibo de pago para imprimir o guardar como PDF (no es una factura ni un CFDI). */
export default function Recibo() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<any>(null);
  const [logo, setLogo] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get(`/clientes/pagos/${id}/recibo`).then(async (x) => {
      setR(x);
      if (x.despacho.tiene_logo) try { setLogo(URL.createObjectURL((await api.blob("/organizacion/logo")).blob)); } catch {}
    }).catch((e) => setError(e.message));
  }, [id]);
  if (!r) return <div className="p-8"><Aviso>{error}</Aviso></div>;
  const fecha = new Date(r.fecha + "T12:00").toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" });
  return (
    <div className="min-h-screen bg-crema/60 py-8 print:bg-white print:py-0">
      <div className="mx-auto mb-4 flex max-w-2xl justify-between px-4 print:hidden">
        <button onClick={() => history.back()} className="text-sm font-semibold text-turquesa-700">← Volver</button>
        <button className="btn-turquesa" onClick={() => window.print()}>Imprimir o guardar PDF</button>
      </div>
      <article className="relative mx-auto max-w-2xl rounded-2xl bg-white p-10 shadow-sm print:rounded-none print:shadow-none">
        {r.cancelado && <div className="absolute inset-0 flex items-center justify-center"><span className="-rotate-12 rounded-xl border-4 border-red-600/60 px-6 py-2 text-5xl font-black text-red-600/60">CANCELADO</span></div>}
        <header className="flex items-start justify-between gap-6 border-b border-slate-200 pb-6">
          <div className="flex items-center gap-3">{logo && <img src={logo} alt="" className="h-14 w-auto" />}<p className="text-lg font-extrabold text-marino">{r.despacho.nombre}</p></div>
          <div className="text-right"><p className="text-xs uppercase tracking-widest text-slate-500">Recibo de pago</p>
            <p className="text-2xl font-black text-marino">No. {String(r.folio).padStart(5, "0")}</p><p className="text-sm text-slate-600">{fecha}</p></div>
        </header>
        <section className="mt-6 space-y-1 text-sm">
          <p className="text-xs uppercase tracking-widest text-slate-500">Recibimos de</p>
          <p className="text-lg font-bold text-marino">{r.cliente.nombre}</p>
          {r.cliente.rfc && <p className="font-mono text-slate-600">RFC {r.cliente.rfc}</p>}
          {r.cliente.domicilio && <p className="text-slate-600">{r.cliente.domicilio}</p>}
        </section>
        <section className="mt-6 rounded-xl bg-crema/60 p-5">
          <div className="flex items-baseline justify-between gap-4"><span className="text-sm text-slate-600">La cantidad de</span><span className="text-3xl font-black text-marino">{mxn(r.monto)}</span></div>
          <p className="mt-1 text-right text-xs font-semibold text-slate-600">({r.monto_letra})</p>
        </section>
        <dl className="mt-6 grid grid-cols-[9rem_1fr] gap-y-2 text-sm">
          <dt className="text-slate-500">Por concepto de</dt><dd className="font-semibold text-slate-800">{r.concepto}</dd>
          <dt className="text-slate-500">Forma de pago</dt><dd>{r.metodo}{r.referencia ? ` · ${r.referencia}` : ""}</dd>
          {r.nota && <><dt className="text-slate-500">Nota</dt><dd>{r.nota}</dd></>}
          <dt className="text-slate-500">Saldo pendiente</dt><dd>{mxn(r.saldo_despues)}</dd>
          {r.cancelado && <><dt className="text-red-600">Cancelado</dt><dd className="text-red-600">{r.motivo_cancelacion}</dd></>}
        </dl>
        <footer className="mt-16 grid grid-cols-2 gap-10 text-center text-xs text-slate-500">
          <div><div className="mb-1 border-t border-slate-400" />Recibió{r.recibio ? `: ${r.recibio}` : ""}</div>
          <div><div className="mb-1 border-t border-slate-400" />Sello del despacho</div>
        </footer>
        <p className="mt-8 text-center text-[11px] text-slate-400">Este recibo es un comprobante interno de pago y no sustituye a un comprobante fiscal (CFDI).</p>
      </article>
      <p className="mt-4 text-center text-xs text-slate-400 print:hidden"><Link href="/clientes">Clientes</Link></p>
    </div>
  );
}
