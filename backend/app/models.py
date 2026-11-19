"""Modelo de datos. Todo importe es NUMERIC(14,2) / Decimal; las claves son texto."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

DINERO = Numeric(14, 2)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Organizacion(Base):
    __tablename__ = "organizaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    # Marca del cliente: se guarda en la base (no en disco) ya normalizada a PNG.
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    logo_actualizado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # La administra quien opera Nomira: «suspendida» impide entrar a todos sus usuarios.
    estado: Mapped[str] = mapped_column(String(20), default="activa", server_default="activa")
    motivo_suspension: Mapped[str | None] = mapped_column(String(300))


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    hash_contrasena: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str] = mapped_column(String(20))  # administrador | analista | consulta
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Sube al cambiar la contraseña o desactivar al usuario: invalida los tokens ya emitidos.
    sesion_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Foto de perfil ya recortada y reducida (JPEG de 256 px, ~15 KB). En la base, no en disco:
    # el disco de algunos alojamientos (p. ej. Render gratuito) se borra al reiniciar.
    foto: Mapped[bytes | None] = mapped_column(LargeBinary)
    # Baja lógica: el usuario desaparece del panel y no puede entrar, pero sus acciones pasadas
    # (correcciones, validaciones, auditoría) conservan su referencia.
    eliminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Catalogo(Base):
    __tablename__ = "catalogos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    versiones: Mapped[list["CatalogoVersion"]] = relationship(
        back_populates="catalogo", order_by="CatalogoVersion.numero", cascade="all, delete-orphan")


class CatalogoVersion(Base):
    """Una versión activa o archivada es inmutable: cambiar el catálogo = crear otra versión."""
    __tablename__ = "catalogo_versiones"
    __table_args__ = (UniqueConstraint("catalogo_id", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    catalogo_id: Mapped[int] = mapped_column(ForeignKey("catalogos.id"), index=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(20), default="borrador")  # borrador | activo | archivado
    origen: Mapped[str] = mapped_column(String(20))  # ocr | manual | copia
    archivo_nombre: Mapped[str | None] = mapped_column(String(300))
    archivo_sha256: Mapped[str | None] = mapped_column(String(64))
    notas: Mapped[str | None] = mapped_column(Text)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    validado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    catalogo: Mapped[Catalogo] = relationship(back_populates="versiones")
    entradas: Mapped[list["CatalogoEntrada"]] = relationship(
        back_populates="version", order_by="CatalogoEntrada.clave", cascade="all, delete-orphan")


class CatalogoEntrada(Base):
    __tablename__ = "catalogo_entradas"
    __table_args__ = (UniqueConstraint("version_id", "clave"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("catalogo_versiones.id", ondelete="CASCADE"), index=True)
    clave: Mapped[str] = mapped_column(String(12))  # texto: conserva ceros iniciales
    descripcion: Mapped[str] = mapped_column(String(400))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    confianza: Mapped[int | None] = mapped_column(Integer)  # confianza OCR 0-100
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False)
    nota: Mapped[str | None] = mapped_column(String(300))
    pagina: Mapped[int | None] = mapped_column(Integer)
    # La agregó una persona porque no venía en el documento fuente (clave faltante).
    agregada_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    version: Mapped[CatalogoVersion] = relationship(back_populates="entradas")


class Expediente(Base):
    __tablename__ = "expedientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    trabajador_nombre: Mapped[str] = mapped_column(String(200))
    identificador_laboral: Mapped[str | None] = mapped_column(String(40))
    periodo_inicio: Mapped[date] = mapped_column(Date)
    periodo_fin: Mapped[date] = mapped_column(Date)
    quincenas_esperadas: Mapped[int] = mapped_column(Integer)
    catalogo_version_id: Mapped[int] = mapped_column(ForeignKey("catalogo_versiones.id"))
    estado: Mapped[str] = mapped_column(String(30), default="nuevo")
    # nuevo | procesando | pendiente_revision | validado | error
    politica_retroactivos: Mapped[str] = mapped_column(String(40), default="quincena_de_pago")
    decision_plazas: Mapped[str | None] = mapped_column(String(20))  # consolidar | separar
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    validado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notas_validacion: Mapped[str | None] = mapped_column(Text)
    resultado_validado: Mapped[dict | None] = mapped_column(JSON)  # instantánea congelada
    verificacion_ia: Mapped[dict | None] = mapped_column(JSON)  # avance de la verificación con IA
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)
    catalogo_version: Mapped[CatalogoVersion] = relationship()
    documentos: Mapped[list["Documento"]] = relationship(back_populates="expediente", order_by="Documento.id")


class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (UniqueConstraint("expediente_id", "sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expedientes.id"), index=True)
    nombre_original: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    tamano_bytes: Mapped[int] = mapped_column(Integer)
    ruta: Mapped[str] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente | procesando | procesado | error
    error: Mapped[str | None] = mapped_column(Text)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    num_paginas: Mapped[int | None] = mapped_column(Integer)
    subido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    procesado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expediente: Mapped[Expediente] = relationship(back_populates="documentos")
    paginas: Mapped[list["Pagina"]] = relationship(cascade="all, delete-orphan", order_by="Pagina.numero")
    recibos: Mapped[list["Recibo"]] = relationship(back_populates="documento", cascade="all, delete-orphan")


class Pagina(Base):
    __tablename__ = "paginas"
    __table_args__ = (UniqueConstraint("documento_id", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(20))  # recibo | informativa | desconocida
    metodo: Mapped[str] = mapped_column(String(10))  # texto | ocr
    texto: Mapped[str] = mapped_column(Text)
    ancho: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    alto: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    confianza_ocr: Mapped[int | None] = mapped_column(Integer)


class Recibo(Base):
    __tablename__ = "recibos"
    __table_args__ = (UniqueConstraint("documento_id", "pagina_numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expedientes.id"), index=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id", ondelete="CASCADE"), index=True)
    pagina_numero: Mapped[int] = mapped_column(Integer)
    num_recibo: Mapped[str | None] = mapped_column(String(40))
    trabajador_nombre: Mapped[str | None] = mapped_column(String(200))
    clave_servidor: Mapped[str | None] = mapped_column(String(40))
    plaza: Mapped[str | None] = mapped_column(String(60))
    periodo_texto: Mapped[str | None] = mapped_column(String(100))
    periodo_inicio: Mapped[date | None] = mapped_column(Date)
    periodo_fin: Mapped[date | None] = mapped_column(Date)
    total_percepciones: Mapped[Decimal | None] = mapped_column(DINERO)
    total_deducciones: Mapped[Decimal | None] = mapped_column(DINERO)
    total_neto: Mapped[Decimal | None] = mapped_column(DINERO)
    confianza: Mapped[int | None] = mapped_column(Integer)
    # Decisión humana sobre el recibo (duplicado, complementario, otro trabajador, descuadre…)
    decision: Mapped[str | None] = mapped_column(String(20))  # incluir | excluir
    decision_motivo: Mapped[str | None] = mapped_column(Text)
    decision_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    decision_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Segunda lectura independiente con IA (opcional): solo compara, nunca modifica importes.
    verificacion_ia: Mapped[dict | None] = mapped_column(JSON)
    documento: Mapped[Documento] = relationship(back_populates="recibos")
    filas: Mapped[list["Fila"]] = relationship(
        back_populates="recibo", cascade="all, delete-orphan", order_by="Fila.orden")


class Fila(Base):
    """Fila de percepciones o deducciones. *_leido es la lectura original e inmutable;
    clave/concepto/importe son los valores vigentes (lectura + correcciones)."""
    __tablename__ = "filas"
    id: Mapped[int] = mapped_column(primary_key=True)
    recibo_id: Mapped[int] = mapped_column(ForeignKey("recibos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(15))  # percepcion | deduccion
    orden: Mapped[int] = mapped_column(Integer)
    origen: Mapped[str] = mapped_column(String(10), default="lectura")  # lectura | manual
    clave_leida: Mapped[str | None] = mapped_column(String(40))
    concepto_leido: Mapped[str | None] = mapped_column(String(300))
    importe_leido_texto: Mapped[str | None] = mapped_column(String(60))
    clave: Mapped[str | None] = mapped_column(String(40))
    concepto: Mapped[str | None] = mapped_column(String(300))
    importe: Mapped[Decimal | None] = mapped_column(DINERO)  # NULL = ilegible/faltante, nunca 0
    confianza: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[list | None] = mapped_column(JSON)  # [x0,y0,x1,y1] en puntos de página
    corregida: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmada: Mapped[bool] = mapped_column(Boolean, default=False)
    recibo: Mapped[Recibo] = relationship(back_populates="filas")


class Correccion(Base):
    __tablename__ = "correcciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expedientes.id"), index=True)
    recibo_id: Mapped[int | None] = mapped_column(ForeignKey("recibos.id", ondelete="SET NULL"))
    fila_id: Mapped[int | None] = mapped_column(ForeignKey("filas.id", ondelete="SET NULL"))
    entidad: Mapped[str] = mapped_column(String(20))  # fila | recibo
    campo: Mapped[str] = mapped_column(String(40))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_nuevo: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    usuario_email: Mapped[str] = mapped_column(String(254))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    referencia: Mapped[dict | None] = mapped_column(JSON)  # documento, página, clave: sobrevive a reprocesos


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    usuario_email: Mapped[str | None] = mapped_column(String(254))
    accion: Mapped[str] = mapped_column(String(60))
    entidad: Mapped[str | None] = mapped_column(String(40))
    entidad_id: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(60))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class Solicitud(Base):
    """Prospecto que pide informes o una suscripción desde la página de inicio (formulario público)."""
    __tablename__ = "solicitudes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20))  # informes | suscripcion
    nombre: Mapped[str] = mapped_column(String(200))
    empresa: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(40))
    expedientes_mes: Mapped[str | None] = mapped_column(String(20))
    mensaje: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="nueva")  # nueva | atendida
    nota: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(60))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)
    atendida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminPlataforma(Base):
    """Quien opera Nomira. NO pertenece a ninguna organización: su sesión no sirve en la API de
    los clientes, así que no puede ver expedientes, recibos ni documentos."""
    __tablename__ = "administradores_plataforma"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    hash_contrasena: Mapped[str] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    sesion_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketSoporte(Base):
    """Conversación de soporte entre una organización cliente y quien opera Nomira."""
    __tablename__ = "tickets_soporte"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    asunto: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(20), default="abierto")  # abierto | cerrado
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)
    leido_cliente: Mapped[bool] = mapped_column(Boolean, default=True)
    leido_plataforma: Mapped[bool] = mapped_column(Boolean, default=False)
    mensajes: Mapped[list["MensajeSoporte"]] = relationship(
        back_populates="ticket", order_by="MensajeSoporte.id", cascade="all, delete-orphan")


class MensajeSoporte(Base):
    __tablename__ = "mensajes_soporte"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets_soporte.id", ondelete="CASCADE"), index=True)
    autor_tipo: Mapped[str] = mapped_column(String(15))  # cliente | plataforma
    autor_nombre: Mapped[str] = mapped_column(String(200))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    texto: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    ticket: Mapped[TicketSoporte] = relationship(back_populates="mensajes")


class PeriodoSuscripcion(Base):
    """Un periodo contratado (o de prueba) de una organización cliente. Lo administra quien opera
    Nomira; el historial completo queda para saber qué se vendió y cuándo vence."""
    __tablename__ = "periodos_suscripcion"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    plan: Mapped[str] = mapped_column(String(15))  # prueba | mensual | semestral | anual
    inicio: Mapped[date] = mapped_column(Date)
    fin: Mapped[date] = mapped_column(Date)  # último día incluido
    monto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    pagado: Mapped[bool] = mapped_column(Boolean, default=False)
    pagado_en: Mapped[date | None] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(String(500))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class CorreoEnviado(Base):
    """Bitácora de correos que envía Nomira. Nunca guarda el cuerpo (puede llevar una contraseña
    temporal). `llave` evita enviar dos veces el mismo recordatorio (única cuando no es nula)."""
    __tablename__ = "correos_enviados"
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40))  # bienvenida | recordatorio_vencimiento | prueba
    organizacion_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    periodo_id: Mapped[int | None] = mapped_column(ForeignKey("periodos_suscripcion.id", ondelete="SET NULL"))
    llave: Mapped[str | None] = mapped_column(String(80), unique=True)
    destinatarios: Mapped[str] = mapped_column(String(1000))
    asunto: Mapped[str] = mapped_column(String(300))
    estado: Mapped[str] = mapped_column(String(20))  # enviando | enviado | error
    error: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


# ---------------------------------------------------------------------------------------------
# Módulos contratados por organización
# ---------------------------------------------------------------------------------------------

class OrganizacionModulo(Base):
    """Un módulo de Nomira para una organización. Sin fila, se aplica el valor por defecto del
    módulo (services/modulos.py). «contratado» lo fija quien opera la plataforma; «activo», el
    administrador del despacho (solo entre los contratados). Desactivar nunca borra datos."""
    __tablename__ = "organizacion_modulos"
    __table_args__ = (UniqueConstraint("organizacion_id", "modulo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    modulo: Mapped[str] = mapped_column(String(30))  # nomina | evidencia
    contratado: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


# ---------------------------------------------------------------------------------------------
# Nomira Evidencia (módulo independiente: no usa ninguna tabla de nómina)
# ---------------------------------------------------------------------------------------------

class EvAsunto(Base):
    __tablename__ = "ev_asuntos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    cliente: Mapped[str | None] = mapped_column(String(200))
    tipo_caso: Mapped[str | None] = mapped_column(String(120))  # texto libre: ninguna materia impuesta
    jurisdiccion: Mapped[str | None] = mapped_column(String(160))
    identificador_interno: Mapped[str | None] = mapped_column(String(80))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    notas: Mapped[str | None] = mapped_column(Text)
    campos: Mapped[dict | None] = mapped_column(JSON)  # campos adicionales que defina el despacho
    contradicciones_descartadas: Mapped[list | None] = mapped_column(JSON)  # pares "idA-idB": «no es contradicción»
    # Decisión de una persona sobre cada posible diferencia: {"idA-idB": {"decision", "por", "en", "nota"}}
    decisiones_diferencias: Mapped[dict | None] = mapped_column(JSON)
    # Jurisdicción en campos separados («jurisdiccion» se conserva tal como se capturó antes)
    ambito: Mapped[str | None] = mapped_column(String(10))  # federal | local
    entidad_federativa: Mapped[str | None] = mapped_column(String(40))
    municipio_distrito: Mapped[str | None] = mapped_column(String(160))
    organo: Mapped[str | None] = mapped_column(String(200))  # juzgado, tribunal u órgano
    expediente_judicial: Mapped[str | None] = mapped_column(String(80))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class EvDocumento(Base):
    __tablename__ = "ev_documentos"
    __table_args__ = (UniqueConstraint("asunto_id", "sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    asunto_id: Mapped[int] = mapped_column(ForeignKey("ev_asuntos.id", ondelete="CASCADE"), index=True)
    nombre_original: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    tamano_bytes: Mapped[int] = mapped_column(Integer)
    formato: Mapped[str] = mapped_column(String(10))  # pdf | png | jpeg | webp
    ruta: Mapped[str] = mapped_column(String(500))
    # Lectura: recibido (del cliente, sin leer) | pendiente | procesando | leido | requiere_revision | error
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    error: Mapped[str | None] = mapped_column(Text)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    num_paginas: Mapped[int | None] = mapped_column(Integer)
    tipo: Mapped[str | None] = mapped_column(String(60))  # clasificación confirmada por una persona
    tipo_sugerido: Mapped[str | None] = mapped_column(String(60))
    fecha_documento: Mapped[date | None] = mapped_column(Date)  # confirmada por una persona
    fecha_sugerida: Mapped[date | None] = mapped_column(Date)
    clasificado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    origen: Mapped[str] = mapped_column(String(20), default="carga")  # carga | cliente (enlace de solicitud)
    solicitud_id: Mapped[int | None] = mapped_column(ForeignKey("ev_solicitudes.id", ondelete="SET NULL"), index=True)
    solicitado_como: Mapped[str | None] = mapped_column(String(200))  # documento de la lista que el cliente dijo enviar
    # interno (del despacho) | compartible (con el cliente) | restringido (solo administradores, responsable y quien lo cargó)
    visibilidad: Mapped[str] = mapped_column(String(15), default="interno", server_default="interno")
    resumen_lectura: Mapped[dict | None] = mapped_column(JSON)  # qué encontró la última lectura
    aceptado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    aceptado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origen_ref: Mapped[dict | None] = mapped_column(JSON)
    subido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    leido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paginas: Mapped[list["EvPagina"]] = relationship(cascade="all, delete-orphan", order_by="EvPagina.numero")


class EvPagina(Base):
    __tablename__ = "ev_paginas"
    __table_args__ = (UniqueConstraint("documento_id", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("ev_documentos.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    metodo: Mapped[str] = mapped_column(String(10))  # texto | ocr
    texto: Mapped[str] = mapped_column(Text)
    confianza_ocr: Mapped[int | None] = mapped_column(Integer)
    ancho: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    alto: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class EvHecho(Base):
    """Hecho con fuente. Estados: por_revisar | confirmado | editado | descartado. Solo una persona
    puede llevarlo a confirmado/editado, y solo si tiene documento fuente."""
    __tablename__ = "ev_hechos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    asunto_id: Mapped[int] = mapped_column(ForeignKey("ev_asuntos.id", ondelete="CASCADE"), index=True)
    descripcion: Mapped[str] = mapped_column(Text)
    # fecha_evento | fecha_documento | importe | persona | lugar | administrativo | otro
    tipo_dato: Mapped[str] = mapped_column(String(20), default="otro", server_default="otro")
    tema: Mapped[str | None] = mapped_column(String(40))  # qué evento describe (p. ej. separacion)
    valor_original: Mapped[str | None] = mapped_column(String(300))  # texto tal como aparece
    valor: Mapped[str | None] = mapped_column(String(300))  # dato normalizado para mostrar
    atribucion: Mapped[str | None] = mapped_column(String(200))  # quién lo afirma: «La clienta refiere», «El borrador propone»
    calidad: Mapped[str | None] = mapped_column(String(10))  # buena | revisar | baja (de la extracción, no del hecho)
    motivo_descarte: Mapped[str | None] = mapped_column(String(30))  # no_relevante | (vacío: descartado sin más)
    fecha: Mapped[date | None] = mapped_column(Date)
    fecha_texto: Mapped[str | None] = mapped_column(String(80))  # como aparece en el documento
    personas: Mapped[list | None] = mapped_column(JSON)
    importe: Mapped[Decimal | None] = mapped_column(DINERO)
    dato: Mapped[str | None] = mapped_column(String(300))  # otro dato estructurado
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("ev_documentos.id", ondelete="SET NULL"), index=True)
    pagina: Mapped[int | None] = mapped_column(Integer)
    fragmento: Mapped[str | None] = mapped_column(Text)  # texto literal de origen
    bbox: Mapped[list | None] = mapped_column(JSON)
    confianza: Mapped[int | None] = mapped_column(Integer)
    origen: Mapped[str] = mapped_column(String(15), default="automatico")  # automatico | manual
    estado: Mapped[str] = mapped_column(String(15), default="por_revisar")
    original: Mapped[dict | None] = mapped_column(JSON)  # propuesta automática tal como se generó
    revisado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class EvPunto(Base):
    """Fila de la matriz de evidencia: un hecho que el despacho busca acreditar."""
    __tablename__ = "ev_puntos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    asunto_id: Mapped[int] = mapped_column(ForeignKey("ev_asuntos.id", ondelete="CASCADE"), index=True)
    descripcion: Mapped[str] = mapped_column(Text)
    # pendiente_evidencia | respaldado | parcial | contradictorio — lo decide una persona
    estado: Mapped[str] = mapped_column(String(25), default="pendiente_evidencia")
    estado_decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    estado_decidido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notas: Mapped[str | None] = mapped_column(Text)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    vinculos: Mapped[list["EvVinculo"]] = relationship(cascade="all, delete-orphan", order_by="EvVinculo.id")


class EvVinculo(Base):
    __tablename__ = "ev_vinculos"
    id: Mapped[int] = mapped_column(primary_key=True)
    punto_id: Mapped[int] = mapped_column(ForeignKey("ev_puntos.id", ondelete="CASCADE"), index=True)
    hecho_id: Mapped[int | None] = mapped_column(ForeignKey("ev_hechos.id", ondelete="CASCADE"))
    documento_id: Mapped[int] = mapped_column(ForeignKey("ev_documentos.id", ondelete="CASCADE"))
    pagina: Mapped[int | None] = mapped_column(Integer)
    nota: Mapped[str | None] = mapped_column(String(500))
    # Qué hace esta fuente respecto al punto, según el abogado: sin_evaluar | apoya | contradice | no_basta
    relacion: Mapped[str] = mapped_column(String(15), default="sin_evaluar", server_default="sin_evaluar")
    relacion_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    relacion_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class EvPendiente(Base):
    __tablename__ = "ev_pendientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    asunto_id: Mapped[int] = mapped_column(ForeignKey("ev_asuntos.id", ondelete="CASCADE"), index=True)
    descripcion: Mapped[str] = mapped_column(Text)
    responsable: Mapped[str | None] = mapped_column(String(200))  # persona del despacho o del cliente
    fecha_seguimiento: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(15), default="pendiente")  # pendiente | solicitado | recibido | cancelado
    nota: Mapped[str | None] = mapped_column(Text)  # interna: no sale en la lista para el cliente
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class EvSolicitud(Base):
    """Enlace para que un cliente SUBA documentos a un asunto. Nunca permite consultar nada.
    El token no se guarda: solo su huella SHA-256 (y 4 caracteres para reconocerlo)."""
    __tablename__ = "ev_solicitudes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    asunto_id: Mapped[int] = mapped_column(ForeignKey("ev_asuntos.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    mensaje: Mapped[str | None] = mapped_column(Text)  # lo ve el cliente
    documentos: Mapped[list | None] = mapped_column(JSON)  # lista de lo que se pide (lo ve el cliente)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_pista: Mapped[str] = mapped_column(String(8))
    requiere_codigo: Mapped[bool] = mapped_column(Boolean, default=True)
    max_archivos: Mapped[int] = mapped_column(Integer, default=20)
    archivos_recibidos: Mapped[int] = mapped_column(Integer, default=0)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    codigo_hash: Mapped[str | None] = mapped_column(String(64))
    codigo_expira_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    codigo_intentos: Mapped[int] = mapped_column(Integer, default=0)
    codigo_enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    codigos_enviados: Mapped[int] = mapped_column(Integer, default=0)
    primer_acceso_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_acceso_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_carga_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
