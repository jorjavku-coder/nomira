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
