"""Clientes del despacho: directorio único, vínculos con los módulos y estado de cuenta.

- Un cliente se captura una vez y cada módulo lo elige (cr_cliente_id). Los módulos conservan su propia copia del
  nombre para no romper lo que ya existe; al vincular se actualiza.
- Estado de cuenta: los pagos indicados a un cargo se aplican a ese cargo; los pagos «a cuenta» (y lo que sobre)
  se aplican a los cargos más antiguos. Lo que sobre al final es saldo a favor del cliente.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from ..afore import cifrado, identificadores

CERO = Decimal("0.00")
TIPOS_DOC = {"identificacion": "Identificación oficial", "constancia": "Constancia de situación fiscal", "domicilio": "Comprobante de domicilio",
             "contrato": "Contrato de servicios", "poder": "Poder notarial", "otro": "Otro documento"}
METODOS = {"transferencia": "Transferencia", "efectivo": "Efectivo", "tarjeta": "Tarjeta", "cheque": "Cheque", "deposito": "Depósito", "otro": "Otro"}
RFC = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
CURP = re.compile(r"^[A-Z][AEIOUX][A-Z]{2}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d$")

# Lo que cada módulo guarda del cliente: (módulo que debe estar activo, modelo, campo con el nombre, ruta en el panel)
VINCULOS = {
    "agenda": ("agenda", m.AgAsunto, "titulo", "/agenda/asuntos/{id}", "Asunto en Agenda"),
    "evidencia": ("evidencia", m.EvAsunto, "nombre", "/evidencia/{id}", "Carpeta de Evidencia"),
    "afore": ("afore", m.AfCliente, "nombre", "/afore/clientes/{id}", "Cliente en AFORE"),
    "nomina": ("nomina", m.Expediente, "trabajador_nombre", "/expedientes/{id}", "Expediente de nómina"),
    "leads": ("leads", m.LdProspecto, "nombre", "/leads/prospectos/{id}", "Prospecto en Leads"),
}


def plano(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z0-9Ñ& ]", " ", s)
    s = re.sub(r"\b(SA|DE|CV|S|A|C|V|SC|RL|SAPI|SAB)\b", " ", s) if len(s) > 12 else s
    return re.sub(r"\s+", " ", s).strip()


def txt(v: str | None, n: int) -> str | None:
    v = re.sub(r"\s+", " ", (v or "")).strip()
    return v[:n] or None


def limpiar_rfc(v: str | None) -> str | None:
    v = re.sub(r"[\s-]", "", (v or "").upper())
    if not v:
        return None
    if not RFC.match(v):
        raise HTTPException(422, "El RFC no tiene un formato válido (12 caracteres para persona moral, 13 para persona física).")
    return v


def limpiar_curp(v: str | None) -> str | None:
    v = re.sub(r"\s", "", (v or "").upper())
    if not v:
        return None
    if not CURP.match(v):
        raise HTTPException(422, "La CURP no tiene un formato válido (18 caracteres).")
    return v


def sumar_meses(d: date, n: int) -> date:
    import calendar
    a, mes = divmod(d.month - 1 + n, 12)
    anio, mes = d.year + a, mes + 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def de_org(db: Session, cid: int | None, org: int) -> m.CrCliente | None:
    """Para los módulos: valida que el cliente elegido sea del mismo despacho."""
    if not cid:
        return None
    c = db.get(m.CrCliente, cid)
    if not c or c.organizacion_id != org:
        raise HTTPException(404, "Cliente no encontrado.")
    return c


def curp(c: m.CrCliente) -> str | None:
    return cifrado.descifrar(c.curp_cifrado)


def fijar_curp(c: m.CrCliente, v: str | None) -> None:
    v = limpiar_curp(v)
    c.curp_cifrado, c.curp_pista = cifrado.cifrar(v), identificadores.pista_curp(v) if v else None


# ------------------------------------------------------------------ estado de cuenta

@dataclass
class Cuenta:
    cargos: list[dict] = field(default_factory=list)
    cargado: Decimal = CERO
    pagado: Decimal = CERO
    vencido: Decimal = CERO
    por_vencer: Decimal = CERO
    a_favor: Decimal = CERO
    proximo: date | None = None

    @property
    def saldo(self) -> Decimal:
        return self.cargado - self.pagado

    def resumen(self) -> dict:
        return {"cargado": str(self.cargado), "pagado": str(self.pagado), "saldo": str(max(self.saldo, CERO)), "vencido": str(self.vencido),
                "por_vencer": str(self.por_vencer), "a_favor": str(self.a_favor), "proximo_vencimiento": self.proximo.isoformat() if self.proximo else None}


def cuenta(cargos: list[m.CrCargo], pagos: list[m.CrPago], hoy: date) -> Cuenta:
    vivos = sorted([c for c in cargos if c.cancelado_en is None], key=lambda c: (c.vence, c.id))
    validos = [p for p in pagos if p.cancelado_en is None]
    aplicado: dict[int, Decimal] = defaultdict(lambda: CERO)
    pool = CERO
    ids = {c.id for c in vivos}
    for p in validos:
        if p.cargo_id in ids:
            c = next(x for x in vivos if x.id == p.cargo_id)
            entra = min(p.monto, c.monto - aplicado[c.id])
            aplicado[c.id] += entra
            pool += p.monto - entra
        else:
            pool += p.monto
    for c in vivos:  # lo «a cuenta» va a lo más antiguo
        if pool <= 0:
            break
        entra = min(pool, c.monto - aplicado[c.id])
        aplicado[c.id] += entra
        pool -= entra
    r = Cuenta(a_favor=pool)
    for c in sorted(cargos, key=lambda c: (c.vence, c.id)):
        pend = CERO if c.cancelado_en else c.monto - aplicado[c.id]
        if c.cancelado_en:
            estado = "cancelado"
        elif pend <= 0:
            estado = "pagado"
        elif c.vence < hoy:
            estado = "vencido"
        elif aplicado[c.id] > 0:
            estado = "parcial"
        else:
            estado = "pendiente"
        if not c.cancelado_en:
            r.cargado += c.monto
            if pend > 0 and c.vence < hoy:
                r.vencido += pend
            elif pend > 0:
                r.por_vencer += pend
                r.proximo = min(r.proximo or c.vence, c.vence)
        r.cargos.append({"id": c.id, "concepto": c.concepto, "monto": str(c.monto), "pagado": str(aplicado[c.id]), "pendiente": str(max(pend, CERO)),
                         "fecha": c.fecha.isoformat(), "vence": c.vence.isoformat(), "estado": estado, "relacionado": c.relacionado,
                         "grupo": c.grupo, "motivo_cancelacion": c.motivo_cancelacion})
    r.pagado = sum((p.monto for p in validos), CERO)
    return r


def cuentas_org(db: Session, org: int, hoy: date) -> dict[int, Cuenta]:
    cargos, pagos = defaultdict(list), defaultdict(list)
    for c in db.scalars(select(m.CrCargo).where(m.CrCargo.organizacion_id == org)):
        cargos[c.cliente_id].append(c)
    for p in db.scalars(select(m.CrPago).where(m.CrPago.organizacion_id == org)):
        pagos[p.cliente_id].append(p)
    return {cid: cuenta(cargos[cid], pagos[cid], hoy) for cid in set(cargos) | set(pagos)}


def siguiente_folio(db: Session, org: int) -> int:
    db.execute(select(func.pg_advisory_xact_lock(910_000_000 + org)))
    return (db.scalar(select(func.max(m.CrPago.folio)).where(m.CrPago.organizacion_id == org)) or 0) + 1


# ------------------------------------------------------------------ vínculos con los módulos

def vinculos(db: Session, c: m.CrCliente) -> list[dict]:
    activos = set(modulos.activos(db, c.organizacion_id))
    r = []
    for clave, (mod, modelo, campo, ruta, etiqueta) in VINCULOS.items():
        if mod not in activos:
            continue
        for x in db.scalars(select(modelo).where(modelo.organizacion_id == c.organizacion_id, modelo.cr_cliente_id == c.id).order_by(modelo.id.desc()).limit(100)):
            item = {"modulo": clave, "etiqueta": etiqueta, "id": x.id, "titulo": getattr(x, campo), "ruta": ruta.format(id=x.id)}
            if clave == "agenda":
                item["detalle"] = " · ".join(t for t in (x.numero, x.tribunal, x.estado) if t)
            elif clave == "evidencia":
                item["detalle"] = " · ".join(t for t in (x.expediente_judicial, x.tipo_caso) if t)
            elif clave == "nomina":
                item["detalle"] = f"{x.periodo_inicio:%d/%m/%Y} – {x.periodo_fin:%d/%m/%Y} · {x.estado}"
            elif clave == "afore":
                casos = db.scalars(select(m.AfCaso).where(m.AfCaso.cliente_id == x.id)).all()
                item["detalle"] = f"{len(casos)} caso(s)"
                item["casos"] = [{"id": k.id, "ruta": f"/afore/casos/{k.id}", "estado": k.estado} for k in casos]
            elif clave == "leads":
                item["detalle"] = x.servicio_contratado or "Prospecto"
            r.append(item)
    return r


def vincular(db: Session, org: int, modulo: str, rid: int, c: m.CrCliente | None) -> None:
    if modulo not in VINCULOS:
        raise HTTPException(422, "Módulo desconocido.")
    mod, modelo, campo, *_ = VINCULOS[modulo]
    if mod not in modulos.activos(db, org):
        raise HTTPException(409, "Ese módulo no está activo para su despacho.")
    x = db.get(modelo, rid)
    if not x or x.organizacion_id != org:
        raise HTTPException(404, "No encontrado.")
    x.cr_cliente_id = c.id if c else None
    if c and modulo == "evidencia":
        x.cliente = c.nombre[:200]
    if c and modulo == "afore":  # completa lo que falte en AFORE sin pisar lo capturado ahí
        x.email = x.email or c.email
        x.telefono = x.telefono or c.telefono
        if not x.curp_cifrado and c.curp_cifrado:
            x.curp_cifrado, x.curp_pista = c.curp_cifrado, c.curp_pista


def sugerencias(db: Session, org: int) -> list[dict]:
    """Nombres capturados en los módulos que aún no están ligados al directorio, agrupados por nombre."""
    activos = set(modulos.activos(db, org))
    grupos: dict[str, dict] = {}
    existentes = {plano(c.nombre): c for c in db.scalars(select(m.CrCliente).where(m.CrCliente.organizacion_id == org))}

    def agregar(nombre: str | None, modulo: str, rid: int, titulo: str, extra: dict | None = None):
        k = plano(nombre)
        if len(k) < 3:
            return
        g = grupos.setdefault(k, {"nombre": re.sub(r"\s+", " ", nombre).strip(), "items": [], "datos": {}})
        g["items"].append({"modulo": modulo, "id": rid, "titulo": titulo, "etiqueta": VINCULOS[modulo][4]})
        for kk, vv in (extra or {}).items():
            if vv and not g["datos"].get(kk):
                g["datos"][kk] = vv

    if "evidencia" in activos:
        for x in db.scalars(select(m.EvAsunto).where(m.EvAsunto.organizacion_id == org, m.EvAsunto.cr_cliente_id.is_(None), m.EvAsunto.cliente.is_not(None))):
            agregar(x.cliente, "evidencia", x.id, x.nombre)
    if "afore" in activos:
        for x in db.scalars(select(m.AfCliente).where(m.AfCliente.organizacion_id == org, m.AfCliente.cr_cliente_id.is_(None))):
            agregar(x.nombre, "afore", x.id, x.nombre, {"email": x.email, "telefono": x.telefono})
    if "leads" in activos:
        for x in db.scalars(select(m.LdProspecto).where(m.LdProspecto.organizacion_id == org, m.LdProspecto.cr_cliente_id.is_(None),
                                                        m.LdProspecto.contratado_en.is_not(None), m.LdProspecto.anonimizado_en.is_(None))):
            agregar(x.nombre, "leads", x.id, x.servicio_contratado or x.nombre, {"email": x.email, "telefono": x.telefono})
    if "nomina" in activos:
        for x in db.scalars(select(m.Expediente).where(m.Expediente.organizacion_id == org, m.Expediente.cr_cliente_id.is_(None))):
            agregar(x.trabajador_nombre, "nomina", x.id, x.trabajador_nombre)
    r = []
    for k, g in grupos.items():
        c = existentes.get(k)
        r.append({**g, "clave": k, "cliente_existente": {"id": c.id, "nombre": c.nombre} if c else None})
    return sorted(r, key=lambda g: (g["cliente_existente"] is None, -len(g["items"]), g["nombre"]))


# ------------------------------------------------------------------ importe con letra (recibos)

_U = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE", "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE",
      "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE", "VEINTE", "VEINTIUN", "VEINTIDÓS", "VEINTITRÉS", "VEINTICUATRO", "VEINTICINCO",
      "VEINTISÉIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE"]
_D = ["", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
_C = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]


def _cientos(n: int) -> str:
    if n == 100:
        return "CIEN"
    c, r = divmod(n, 100)
    partes = [_C[c]] if c else []
    if r < 30:
        partes.append(_U[r])
    else:
        d, u = divmod(r, 10)
        partes.append(_D[d] + (f" Y {_U[u]}" if u else ""))
    return " ".join(p for p in partes if p)


def _entero(n: int) -> str:
    if n == 0:
        return "CERO"
    millones, resto = divmod(n, 1_000_000)
    miles, unidades = divmod(resto, 1000)
    partes = []
    if millones:
        partes.append("UN MILLÓN" if millones == 1 else f"{_entero(millones)} MILLONES")
    if miles:
        partes.append("MIL" if miles == 1 else f"{_cientos(miles)} MIL")
    if unidades:
        partes.append(_cientos(unidades))
    return " ".join(partes)


def importe_con_letra(v: Decimal) -> str:
    pesos = int(v)
    centavos = int((v - pesos) * 100 + Decimal("0.5"))
    letra = _entero(pesos)
    de = " DE" if pesos and pesos % 1_000_000 == 0 else ""
    return f"{letra}{de} {'PESO' if pesos == 1 else 'PESOS'} {centavos:02d}/100 M.N."
