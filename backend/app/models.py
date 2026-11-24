"""Modelo de datos. Todo importe es NUMERIC(14,2) / Decimal; las claves son texto."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text,
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
    # Academia: cursos propios contratados por encima de los incluidos y espacio para videos/SCORM
    ac_cursos_extra: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ac_cuota_medios_mb: Mapped[int | None] = mapped_column(Integer)  # vacío = la general de AcConfig
    # Cómo llegó: «panel» (la dio de alta Nomira) o «registro» (se registró sola con prueba gratis).
    # Solo a las de registro se les bloquea el uso cuando termina la prueba sin plan contratado.
    origen: Mapped[str] = mapped_column(String(15), default="panel", server_default="panel")
    modulos_prueba: Mapped[list | None] = mapped_column(JSON)  # los módulos que eligió para su prueba


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
    # Verificación en dos pasos (TOTP). Secreto cifrado; códigos de respaldo con hash.
    totp_secreto_cifrado: Mapped[str | None] = mapped_column(Text)
    totp_activo_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totp_ultimo_paso: Mapped[int | None] = mapped_column(BigInteger)
    totp_respaldo: Mapped[list | None] = mapped_column(JSON)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)  # cuenta de Google vinculada («sub»)
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
    cr_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cr_clientes.id", ondelete="SET NULL"), index=True)  # directorio de Clientes
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
    # superadministrador: todo el panel, incluido Comercial · soporte: todo excepto Comercial y roles
    rol: Mapped[str] = mapped_column(String(20), default="soporte", server_default="superadministrador")
    # Verificación en dos pasos (TOTP, apps como Google Authenticator). Secreto cifrado; códigos de respaldo con hash.
    totp_secreto_cifrado: Mapped[str | None] = mapped_column(Text)
    totp_activo_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totp_ultimo_paso: Mapped[int | None] = mapped_column(BigInteger)  # evita reusar el mismo código
    totp_respaldo: Mapped[list | None] = mapped_column(JSON)


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
    cr_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cr_clientes.id", ondelete="SET NULL"), index=True)  # directorio de Clientes
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


# ---------------------------------------------------------------------------------------------
# Nomira AFORE (módulo independiente: no usa tablas de Nómina ni de Evidencia)
# ---------------------------------------------------------------------------------------------

class AfConfig(Base):
    """Configuración de Nomira AFORE por organización. El token de WhatsApp se guarda cifrado."""
    __tablename__ = "af_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), unique=True)
    checklists: Mapped[dict | None] = mapped_column(JSON)  # {tipo: [requisito, …]} (vacío = valores de fábrica)
    tipos_extra: Mapped[list | None] = mapped_column(JSON)  # tipos de problema propios del despacho
    reglas_plazo: Mapped[list | None] = mapped_column(JSON)  # [{nombre, dias, fuente, revisado_en}] sugerencias, nunca obligatorias
    wa_phone_number_id: Mapped[str | None] = mapped_column(String(40))
    wa_waba_id: Mapped[str | None] = mapped_column(String(40))
    wa_numero: Mapped[str | None] = mapped_column(String(30))  # número visible, solo para mostrar
    wa_token_cifrado: Mapped[str | None] = mapped_column(Text)
    wa_conectado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    wa_conectado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    curp_oficial_autorizado: Mapped[bool] = mapped_column(Boolean, default=False)  # lo decide la plataforma
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class AfCliente(Base):
    """Persona que se comunica con el despacho. CURP y NSS van cifrados; en pantalla, enmascarados."""
    __tablename__ = "af_clientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    cr_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cr_clientes.id", ondelete="SET NULL"), index=True)  # directorio de Clientes
    telefono: Mapped[str | None] = mapped_column(String(20))  # solo dígitos, con lada de país
    email: Mapped[str | None] = mapped_column(String(254))
    curp_cifrado: Mapped[str | None] = mapped_column(Text)
    curp_pista: Mapped[str | None] = mapped_column(String(12))
    nss_cifrado: Mapped[str | None] = mapped_column(Text)
    nss_pista: Mapped[str | None] = mapped_column(String(8))
    titular_estado: Mapped[str] = mapped_column(String(12), default="vive")  # vive | fallecio | no_se
    relacion: Mapped[str] = mapped_column(String(20), default="titular")  # titular | pensionado | beneficiario | representante | familiar
    preferencia_contacto: Mapped[str] = mapped_column(String(12), default="correo")  # whatsapp | correo | telefono | ninguno
    notas: Mapped[str | None] = mapped_column(Text)  # internas
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class AfConsentimiento(Base):
    """Consentimiento para recibir actualizaciones por un canal: cuándo, cómo, para qué y su revocación."""
    __tablename__ = "af_consentimientos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("af_clientes.id", ondelete="CASCADE"), index=True)
    canal: Mapped[str] = mapped_column(String(12))  # whatsapp | correo
    alcance: Mapped[str] = mapped_column(String(300))
    medio: Mapped[str] = mapped_column(String(40))  # verbal | escrito | portal | mensaje
    otorgado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocado_medio: Mapped[str | None] = mapped_column(String(40))


class AfCaso(Base):
    __tablename__ = "af_casos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("af_clientes.id"), index=True)
    titular_nombre: Mapped[str | None] = mapped_column(String(200))  # si el titular no es quien se comunica
    estado: Mapped[str] = mapped_column(String(20), default="borrador")  # borrador | abierto | esperando | pausado | cerrado
    tipo_problema: Mapped[str] = mapped_column(String(60))
    tipo_otro: Mapped[str | None] = mapped_column(String(200))
    datos: Mapped[dict | None] = mapped_column(JSON)  # {campo: {"valor", "estado"}}: afore, institución, montos…
    identificador_interno: Mapped[str | None] = mapped_column(String(80))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    restringido: Mapped[bool] = mapped_column(Boolean, default=False)  # solo administradores, responsable y quien lo creó
    siguiente_actividad: Mapped[str | None] = mapped_column(String(300))
    siguiente_fecha: Mapped[date | None] = mapped_column(Date)
    siguiente_responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    resumen_interno: Mapped[str | None] = mapped_column(Text)
    portal_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    estado_publico: Mapped[str | None] = mapped_column(String(500))  # lo que el despacho decide mostrar al cliente
    siguiente_paso_publico: Mapped[str | None] = mapped_column(String(500))
    publico_actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class AfRequisito(Base):
    """Elemento del checklist del caso (organización, no lista legal definitiva)."""
    __tablename__ = "af_requisitos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("af_casos.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(25), default="no_solicitado")
    visible_cliente: Mapped[bool] = mapped_column(Boolean, default=True)
    nota: Mapped[str | None] = mapped_column(String(500))  # interna
    nota_cliente: Mapped[str | None] = mapped_column(String(300))  # p. ej. qué corregir
    orden: Mapped[int] = mapped_column(Integer, default=0)
    actualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AfDocumento(Base):
    __tablename__ = "af_documentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("af_casos.id", ondelete="CASCADE"), index=True)
    requisito_id: Mapped[int | None] = mapped_column(ForeignKey("af_requisitos.id", ondelete="SET NULL"))
    nombre_original: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str | None] = mapped_column(String(64))
    ruta: Mapped[str | None] = mapped_column(String(500))  # vacío si es un vínculo a Evidencia (no se duplica)
    formato: Mapped[str | None] = mapped_column(String(10))
    tamano_bytes: Mapped[int | None] = mapped_column(Integer)
    origen: Mapped[str] = mapped_column(String(12), default="despacho")  # despacho | cliente | evidencia
    ev_documento_id: Mapped[int | None] = mapped_column(ForeignKey("ev_documentos.id", ondelete="SET NULL"))
    visible_cliente: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str] = mapped_column(String(25), default="recibido")  # recibido | aceptado | requiere_correccion
    recepcion_confirmada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    datos_capturados: Mapped[dict | None] = mapped_column(JSON)  # lo que una persona leyó: nombre, curp (pista), fechas
    subido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AfActividad(Base):
    """Cronología: solicitudes, respuestas, acuses, llamadas, consultas, notas."""
    __tablename__ = "af_actividades"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("af_casos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    institucion: Mapped[str | None] = mapped_column(String(120))
    canal: Mapped[str | None] = mapped_column(String(60))
    folio: Mapped[str | None] = mapped_column(String(80))
    fecha: Mapped[date] = mapped_column(Date)
    resumen: Mapped[str | None] = mapped_column(Text)  # interno
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("af_documentos.id", ondelete="SET NULL"))
    responde_a_id: Mapped[int | None] = mapped_column(ForeignKey("af_actividades.id", ondelete="SET NULL"))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    modificado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    modificado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AfPlazo(Base):
    """Fechas del caso, siempre con su naturaleza: un plazo legal solo existe si el abogado lo confirma."""
    __tablename__ = "af_plazos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("af_casos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(25))  # legal_confirmado | seguimiento_interno | informado_institucion | estimado
    descripcion: Mapped[str] = mapped_column(String(300))
    fecha: Mapped[date] = mapped_column(Date)
    fuente: Mapped[str | None] = mapped_column(String(300))
    regla: Mapped[str | None] = mapped_column(String(120))  # regla configurable que lo sugirió
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    confirmado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AfPlantilla(Base):
    __tablename__ = "af_plantillas"
    __table_args__ = (UniqueConstraint("organizacion_id", "clave"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    clave: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(120))
    texto: Mapped[str] = mapped_column(String(1000))
    wa_nombre: Mapped[str | None] = mapped_column(String(120))  # nombre de la plantilla aprobada en Meta
    wa_idioma: Mapped[str] = mapped_column(String(10), default="es_MX")
    wa_aprobada: Mapped[bool] = mapped_column(Boolean, default=False)
    envio: Mapped[str] = mapped_column(String(12), default="aprobacion")  # aprobacion | automatico
    actualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class AfMensaje(Base):
    """Mensaje al cliente (o recibido de él). Nunca se marca «enviado» sin respuesta del proveedor."""
    __tablename__ = "af_mensajes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("af_clientes.id", ondelete="SET NULL"), index=True)
    caso_id: Mapped[int | None] = mapped_column(ForeignKey("af_casos.id", ondelete="SET NULL"), index=True)
    canal: Mapped[str] = mapped_column(String(12))  # whatsapp | correo
    direccion: Mapped[str] = mapped_column(String(10), default="saliente")  # saliente | entrante
    plantilla: Mapped[str | None] = mapped_column(String(40))
    texto: Mapped[str] = mapped_column(Text)  # sin el enlace: «[enlace]» se genera al enviar
    # borrador | esperando_aprobacion | enviado | entregado | leido | fallido | cancelado | recibido | por_asignar
    estado: Mapped[str] = mapped_column(String(25))
    motivo: Mapped[str | None] = mapped_column(String(500))  # qué falta para poder enviarlo
    origen: Mapped[str | None] = mapped_column(String(40))  # evento que lo generó
    telefono: Mapped[str | None] = mapped_column(String(20))
    proveedor_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    error: Mapped[str | None] = mapped_column(Text)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    aprobado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    aprobado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entregado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asignado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class AfEventoWebhook(Base):
    """Idempotencia de los webhooks: cada evento se procesa una sola vez aunque el proveedor reintente."""
    __tablename__ = "af_eventos_webhook"
    id: Mapped[int] = mapped_column(primary_key=True)
    llave: Mapped[str] = mapped_column(String(200), unique=True)
    recibido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AfAcceso(Base):
    """Acceso del cliente a su portal. Como en las solicitudes de Evidencia: solo la huella del token."""
    __tablename__ = "af_accesos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("af_clientes.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_pista: Mapped[str] = mapped_column(String(8))
    requiere_codigo: Mapped[bool] = mapped_column(Boolean, default=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    codigo_hash: Mapped[str | None] = mapped_column(String(64))
    codigo_expira_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    codigo_intentos: Mapped[int] = mapped_column(Integer, default=0)
    codigo_enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    codigos_enviados: Mapped[int] = mapped_column(Integer, default=0)
    ultimo_uso_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AfConsultaCurp(Base):
    """Registro de cada intento de consulta OFICIAL de CURP (finalidad y consentimiento)."""
    __tablename__ = "af_consultas_curp"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("af_casos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    finalidad: Mapped[str] = mapped_column(String(300))
    consentimiento: Mapped[bool] = mapped_column(Boolean)
    resultado: Mapped[str] = mapped_column(String(40))  # no_configurado | consultado | error
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AfVinculoEvidencia(Base):
    """Referencia a un documento o hecho de Nomira Evidencia (no se copia el archivo)."""
    __tablename__ = "af_vinculos_evidencia"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("af_casos.id", ondelete="CASCADE"), index=True)
    ev_documento_id: Mapped[int | None] = mapped_column(ForeignKey("ev_documentos.id", ondelete="CASCADE"))
    ev_hecho_id: Mapped[int | None] = mapped_column(ForeignKey("ev_hechos.id", ondelete="CASCADE"))
    nota: Mapped[str | None] = mapped_column(String(300))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# ---------------------------------------------------------------------------------------------
# Nomira Leads (módulo independiente: prospectos, seguimiento y origen de los clientes)
# ---------------------------------------------------------------------------------------------

class LdConfig(Base):
    """Configuración de Nomira Leads por organización. Los tokens y claves se guardan cifrados o
    como huella; nunca vuelven al navegador."""
    __tablename__ = "ld_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), unique=True)
    materias: Mapped[list | None] = mapped_column(JSON)  # materias o servicios que ofrece el despacho
    motivos_perdida: Mapped[list | None] = mapped_column(JSON)
    dias_sin_actividad: Mapped[int] = mapped_column(Integer, default=7)
    # Enlace al aviso de privacidad PROPIO del despacho (responsable de los datos de sus prospectos)
    aviso_privacidad_url: Mapped[str | None] = mapped_column(String(500))
    # Enlace público del formulario general (no es secreto: se publica en el sitio o en redes)
    formulario_token: Mapped[str | None] = mapped_column(String(40), unique=True)
    formulario_activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Clave para recibir prospectos de otros sistemas (Zapier, Make, Google Ads, su sitio web): solo la huella
    entrada_clave_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    entrada_clave_pista: Mapped[str | None] = mapped_column(String(8))
    # WhatsApp Business Platform (Cloud API oficial de Meta)
    wa_phone_number_id: Mapped[str | None] = mapped_column(String(40), index=True)
    wa_numero: Mapped[str | None] = mapped_column(String(30))
    wa_token_cifrado: Mapped[str | None] = mapped_column(Text)
    wa_plantilla: Mapped[str | None] = mapped_column(String(120))  # plantilla aprobada para iniciar conversación
    wa_plantilla_idioma: Mapped[str] = mapped_column(String(10), default="es_MX")
    wa_conectado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Anuncios de clientes potenciales de Meta (Facebook e Instagram)
    meta_page_id: Mapped[str | None] = mapped_column(String(40), index=True)
    meta_page_nombre: Mapped[str | None] = mapped_column(String(200))
    meta_token_cifrado: Mapped[str | None] = mapped_column(Text)
    meta_conectado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class LdEtapa(Base):
    """Etapa del tablero. «ganada» (Contratado) y «perdida» (No contratado) siempre existen."""
    __tablename__ = "ld_etapas"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    clave: Mapped[str | None] = mapped_column(String(30))  # etapas de fábrica: nuevo, contactado, consulta_agendada…
    tipo: Mapped[str] = mapped_column(String(10), default="abierta")  # abierta | ganada | perdida
    orden: Mapped[int] = mapped_column(Integer, default=0)
    archivada: Mapped[bool] = mapped_column(Boolean, default=False)


class LdCampana(Base):
    """Campaña o fuente: un anuncio, un correo masivo del despacho, una publicación, un evento…"""
    __tablename__ = "ld_campanas"
    __table_args__ = (UniqueConstraint("organizacion_id", "codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    canal: Mapped[str] = mapped_column(String(20))
    codigo: Mapped[str] = mapped_column(String(12))  # código corto para atribuir (enlaces y mensajes de WhatsApp)
    enlace_token: Mapped[str] = mapped_column(String(40), unique=True)  # formulario propio de la campaña (público)
    id_externo: Mapped[str | None] = mapped_column(String(80))  # id de la campaña en Meta o Google, si llega
    inversion: Mapped[Decimal | None] = mapped_column(DINERO)  # solo si el despacho la registra
    inicio: Mapped[date | None] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    notas: Mapped[str | None] = mapped_column(String(500))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class LdProspecto(Base):
    __tablename__ = "ld_prospectos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    cr_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cr_clientes.id", ondelete="SET NULL"), index=True)  # directorio de Clientes
    telefono: Mapped[str | None] = mapped_column(String(20))  # solo dígitos, con lada de país
    email: Mapped[str | None] = mapped_column(String(254))
    ciudad: Mapped[str | None] = mapped_column(String(120))
    materia: Mapped[str | None] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    canal: Mapped[str] = mapped_column(String(20), default="otro")
    campana_id: Mapped[int | None] = mapped_column(ForeignKey("ld_campanas.id", ondelete="SET NULL"), index=True)
    origen_detalle: Mapped[dict | None] = mapped_column(JSON)  # utm_*, anuncio, formulario… (sin datos personales)
    entrada: Mapped[str] = mapped_column(String(20), default="manual")  # manual | formulario | whatsapp | meta | integracion
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    etapa_id: Mapped[int] = mapped_column(ForeignKey("ld_etapas.id"), index=True)
    borrador: Mapped[bool] = mapped_column(Boolean, default=False)
    preferencia_contacto: Mapped[str] = mapped_column(String(12), default="whatsapp")  # whatsapp | llamada | correo | ninguno
    motivo_perdida: Mapped[str | None] = mapped_column(String(120))
    motivo_nota: Mapped[str | None] = mapped_column(String(500))
    primera_respuesta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_actividad_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    # Contratación
    contratado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    servicio_contratado: Mapped[str | None] = mapped_column(String(200))
    asunto_titulo: Mapped[str | None] = mapped_column(String(200))
    asunto_referencia: Mapped[str | None] = mapped_column(String(80))
    ev_asunto_id: Mapped[int | None] = mapped_column(ForeignKey("ev_asuntos.id", ondelete="SET NULL"))
    af_caso_id: Mapped[int | None] = mapped_column(ForeignKey("af_casos.id", ondelete="SET NULL"))
    anonimizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class LdConsentimiento(Base):
    """Autorización del prospecto para ser contactado por un canal: fecha, medio, finalidad y revocación."""
    __tablename__ = "ld_consentimientos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    prospecto_id: Mapped[int] = mapped_column(ForeignKey("ld_prospectos.id", ondelete="CASCADE"), index=True)
    canal: Mapped[str] = mapped_column(String(12))  # whatsapp | correo | llamada
    finalidad: Mapped[str] = mapped_column(String(300))
    medio: Mapped[str] = mapped_column(String(30))  # verbal | escrito | formulario_web | formulario_meta | mensaje | integracion
    otorgado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocado_medio: Mapped[str | None] = mapped_column(String(30))


class LdAccion(Base):
    """Próximo paso: llamada, mensaje, consulta, propuesta… Un recordatorio NUNCA envía nada solo."""
    __tablename__ = "ld_acciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    prospecto_id: Mapped[int] = mapped_column(ForeignKey("ld_prospectos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # llamada | mensaje | consulta | propuesta | seguimiento
    descripcion: Mapped[str | None] = mapped_column(String(300))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    hora: Mapped[str | None] = mapped_column(String(5))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    recordatorio: Mapped[bool] = mapped_column(Boolean, default=True)  # aviso dentro de Nomira
    completada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str | None] = mapped_column(String(500))
    completada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    cancelada: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class LdActividad(Base):
    """Historial del prospecto: notas, cambios de etapa, responsable, datos, mensajes y contratación."""
    __tablename__ = "ld_actividades"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    prospecto_id: Mapped[int] = mapped_column(ForeignKey("ld_prospectos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    texto: Mapped[str | None] = mapped_column(Text)
    detalle: Mapped[dict | None] = mapped_column(JSON)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class LdMensaje(Base):
    """Conversación con el prospecto. Nunca se marca «enviado» sin respuesta del proveedor."""
    __tablename__ = "ld_mensajes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    prospecto_id: Mapped[int | None] = mapped_column(ForeignKey("ld_prospectos.id", ondelete="SET NULL"), index=True)
    canal: Mapped[str] = mapped_column(String(12))  # whatsapp | correo
    direccion: Mapped[str] = mapped_column(String(10))  # saliente | entrante
    texto: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(15))  # enviado | entregado | leido | fallido | recibido | por_asignar | manual
    telefono: Mapped[str | None] = mapped_column(String(20))
    proveedor_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    error: Mapped[str | None] = mapped_column(Text)
    respondido: Mapped[bool] = mapped_column(Boolean, default=False)  # para entrantes: ya se atendió
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entregado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class LdEventoExterno(Base):
    """Idempotencia de webhooks de Leads (WhatsApp y anuncios de Meta)."""
    __tablename__ = "ld_eventos_externos"
    id: Mapped[int] = mapped_column(primary_key=True)
    llave: Mapped[str] = mapped_column(String(200), unique=True)
    recibido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# ---------------------------------------------------------------------------------------------
# Nomira Academia (módulo independiente: cursos breves para el equipo del despacho)
# ---------------------------------------------------------------------------------------------

class AcCurso(Base):
    """Curso del despacho (organizacion_id) o de Nomira (organizacion_id vacío, de solo lectura)."""
    __tablename__ = "ac_cursos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    clave: Mapped[str | None] = mapped_column(String(60), unique=True)  # cursos de Nomira
    titulo: Mapped[str] = mapped_column(String(200))
    materia: Mapped[str] = mapped_column(String(120))
    roles: Mapped[list | None] = mapped_column(JSON)  # a quién va dirigido (texto libre)
    instructor: Mapped[str | None] = mapped_column(String(200))
    institucion: Mapped[str | None] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text)
    duracion_min: Mapped[int | None] = mapped_column(Integer)
    modalidad: Mapped[str] = mapped_column(String(15), default="autodirigido")  # autodirigido | en_vivo | combinado
    estado: Mapped[str] = mapped_column(String(12), default="borrador")  # borrador | publicado | archivado
    juridico: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False)
    nota_revision: Mapped[str | None] = mapped_column(String(500))
    asistido_ia: Mapped[bool] = mapped_column(Boolean, default=False)  # exige revisión humana antes de publicar
    calificacion_minima: Mapped[int | None] = mapped_column(Integer)  # vacío: basta con completar las lecciones
    # Catálogo de Nomira (solo cursos globales): incluido para todos o con costo (pago único por despacho)
    acceso: Mapped[str] = mapped_column(String(10), default="incluido", server_default="incluido")  # incluido | pago
    precio: Mapped[Decimal | None] = mapped_column(DINERO)  # MXN antes de IVA
    origen_curso_id: Mapped[int | None] = mapped_column(Integer, index=True)  # curso de la cuenta editora del que se publicó
    entregado_por_nomira: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reconocimiento: Mapped[str] = mapped_column(String(12), default="diploma", server_default="diploma")  # diploma | constancia
    version: Mapped[int] = mapped_column(Integer, default=1)
    contenido_actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    revisado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archivado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AcModulo(Base):
    __tablename__ = "ac_modulos"
    id: Mapped[int] = mapped_column(primary_key=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    archivado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcLeccion(Base):
    """Lección. Se archiva (no se borra) para no perder el avance de quien ya la tomó."""
    __tablename__ = "ac_lecciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id", ondelete="CASCADE"), index=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("ac_modulos.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    texto: Mapped[str | None] = mapped_column(Text)
    video_url: Mapped[str | None] = mapped_column(String(500))
    sesion_url: Mapped[str | None] = mapped_column(String(500))
    transcripcion: Mapped[str | None] = mapped_column(Text)
    recursos: Mapped[list | None] = mapped_column(JSON)  # [{titulo, url}]
    actividad: Mapped[dict | None] = mapped_column(JSON)  # {pregunta, opciones, correcta, explicacion}
    archivo_ruta: Mapped[str | None] = mapped_column(String(500))
    archivo_nombre: Mapped[str | None] = mapped_column(String(300))
    archivo_formato: Mapped[str | None] = mapped_column(String(10))
    archivo_tamano: Mapped[int | None] = mapped_column(Integer)
    # Video subido (además del enlace): se sirve con una URL firmada de corta duración
    video_ruta: Mapped[str | None] = mapped_column(String(500))
    video_nombre: Mapped[str | None] = mapped_column(String(300))
    video_formato: Mapped[str | None] = mapped_column(String(10))
    video_tamano: Mapped[int | None] = mapped_column(BigInteger)
    # Paquete SCORM importado (carpeta extraída) y su página de inicio
    scorm_dir: Mapped[str | None] = mapped_column(String(500))
    scorm_inicio: Mapped[str | None] = mapped_column(String(500))
    scorm_version: Mapped[str | None] = mapped_column(String(10))  # 1.2 | 2004
    scorm_tamano: Mapped[int | None] = mapped_column(BigInteger)
    origen_leccion_id: Mapped[int | None] = mapped_column(Integer)  # para actualizar copias del catálogo
    duracion_min: Mapped[int | None] = mapped_column(Integer)
    archivado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class AcPregunta(Base):
    """Pregunta del cuestionario final del curso."""
    __tablename__ = "ac_preguntas"
    id: Mapped[int] = mapped_column(primary_key=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id", ondelete="CASCADE"), index=True)
    texto: Mapped[str] = mapped_column(String(500))
    opciones: Mapped[list] = mapped_column(JSON)
    correcta: Mapped[int] = mapped_column(Integer)
    explicacion: Mapped[str | None] = mapped_column(String(500))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    archivado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcSesion(Base):
    """Sesión en vivo. Nomira no crea reuniones: el despacho pega el enlace de su plataforma."""
    __tablename__ = "ac_sesiones"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duracion_min: Mapped[int] = mapped_column(Integer, default=60)
    enlace: Mapped[str | None] = mapped_column(String(500))
    grabacion_url: Mapped[str | None] = mapped_column(String(500))
    notas: Mapped[str | None] = mapped_column(String(500))
    cancelada: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))


class AcEquipo(Base):
    __tablename__ = "ac_equipos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(String(300))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AcEquipoMiembro(Base):
    __tablename__ = "ac_equipo_miembros"
    __table_args__ = (UniqueConstraint("equipo_id", "usuario_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("ac_equipos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)


class AcInstructor(Base):
    """Usuarios que pueden crear y editar cursos del despacho (además de los administradores)."""
    __tablename__ = "ac_instructores"
    __table_args__ = (UniqueConstraint("organizacion_id", "usuario_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))


class AcAsignacion(Base):
    """Curso asignado a una persona o a un equipo. Al retirarla se conserva en el historial."""
    __tablename__ = "ac_asignaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    equipo_id: Mapped[int | None] = mapped_column(ForeignKey("ac_equipos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(12), default="obligatorio")  # obligatorio | recomendado
    fecha_sugerida: Mapped[date | None] = mapped_column(Date)
    asignado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    retirada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))


class AcAvance(Base):
    """Avance de una persona en un curso. Nunca se borra al actualizar o archivar el curso."""
    __tablename__ = "ac_avances"
    __table_args__ = (UniqueConstraint("usuario_id", "curso_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id"), index=True)
    iniciado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    ultima_leccion_id: Mapped[int | None] = mapped_column(ForeignKey("ac_lecciones.id", ondelete="SET NULL"))
    ultima_actividad_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calificacion: Mapped[int | None] = mapped_column(Integer)
    constancia_folio: Mapped[str | None] = mapped_column(String(20), unique=True)
    # Copia del curso al completarlo: la constancia no cambia aunque el curso se edite después
    curso_titulo: Mapped[str | None] = mapped_column(String(200))
    curso_version: Mapped[int | None] = mapped_column(Integer)
    curso_duracion_min: Mapped[int | None] = mapped_column(Integer)


class AcAvanceLeccion(Base):
    __tablename__ = "ac_avance_lecciones"
    __table_args__ = (UniqueConstraint("avance_id", "leccion_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    avance_id: Mapped[int] = mapped_column(ForeignKey("ac_avances.id", ondelete="CASCADE"), index=True)
    leccion_id: Mapped[int] = mapped_column(ForeignKey("ac_lecciones.id", ondelete="CASCADE"))
    posicion: Mapped[int] = mapped_column(Integer, default=0)  # desplazamiento o segundo de video donde se quedó
    respuesta: Mapped[int | None] = mapped_column(Integer)
    correcta: Mapped[bool | None] = mapped_column(Boolean)
    completada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scorm_datos: Mapped[dict | None] = mapped_column(JSON)  # estado SCORM (cmi.*) que guarda el paquete
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class AcConfig(Base):
    """Configuración general de Academia (una fila), la administra Nomira desde su panel."""
    __tablename__ = "ac_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    cursos_incluidos: Mapped[int] = mapped_column(Integer, default=5)
    cuota_medios_mb: Mapped[int] = mapped_column(Integer, default=2048)  # por despacho: videos + SCORM
    video_max_mb: Mapped[int] = mapped_column(Integer, default=500)
    scorm_max_mb: Mapped[int] = mapped_column(Integer, default=300)
    org_editora_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id", ondelete="SET NULL"))
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcAcceso(Base):
    """Acceso de un despacho a un curso de Nomira con costo (por compra, cotización o cortesía)."""
    __tablename__ = "ac_accesos"
    __table_args__ = (UniqueConstraint("organizacion_id", "curso_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id", ondelete="CASCADE"), index=True)
    origen: Mapped[str] = mapped_column(String(12))  # compra | comercial | cortesia
    compra_id: Mapped[int | None] = mapped_column(Integer)
    cotizacion_id: Mapped[int | None] = mapped_column(ForeignKey("cm_cotizaciones.id", ondelete="SET NULL"))
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcCompra(Base):
    """Compra en línea (Stripe Checkout) de un curso de Nomira. Solo el webhook la marca pagada."""
    __tablename__ = "ac_compras"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("ac_cursos.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    subtotal: Mapped[Decimal] = mapped_column(DINERO)
    iva: Mapped[Decimal] = mapped_column(DINERO)
    total: Mapped[Decimal] = mapped_column(DINERO)
    estado: Mapped[str] = mapped_column(String(12), default="iniciada")  # iniciada | pagada
    stripe_sesion: Mapped[str | None] = mapped_column(String(120), unique=True)
    referencia: Mapped[str | None] = mapped_column(String(120))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    pagada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcIntento(Base):
    __tablename__ = "ac_intentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    avance_id: Mapped[int] = mapped_column(ForeignKey("ac_avances.id", ondelete="CASCADE"), index=True)
    respuestas: Mapped[dict] = mapped_column(JSON)
    aciertos: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    calificacion: Mapped[int] = mapped_column(Integer)
    aprobado: Mapped[bool] = mapped_column(Boolean)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# ---------------------------------------------------------------------------------------------
# Centro Legal: documentos aprobados y versionados, evidencia de aceptación y solicitudes ARCO
# ---------------------------------------------------------------------------------------------

class LgVersion(Base):
    """Versión de un documento legal. El texto lo aprueban el responsable de Nomira y su abogado; aquí
    solo se publica. Una versión publicada NO se modifica: un cambio es una versión nueva."""
    __tablename__ = "lg_versiones"
    __table_args__ = (UniqueConstraint("documento", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    documento: Mapped[str] = mapped_column(String(40), index=True)  # claves de services/legal.py DOCUMENTOS
    numero: Mapped[int] = mapped_column(Integer)  # consecutivo interno por documento
    version: Mapped[str] = mapped_column(String(30))  # etiqueta visible, p. ej. «1.0»
    titulo: Mapped[str] = mapped_column(String(200))
    contenido: Mapped[str] = mapped_column(Text)  # texto aprobado (Markdown sencillo)
    sha256: Mapped[str | None] = mapped_column(String(64))  # huella del contenido al publicar
    resumen_cambios: Mapped[str | None] = mapped_column(String(1000))
    requiere_aceptacion: Mapped[bool] = mapped_column(Boolean, default=False)  # pide aceptar de nuevo a quien aceptó una anterior
    vigente_desde: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(12), default="borrador")  # borrador | publicada | retirada
    aprobado_por: Mapped[str | None] = mapped_column(String(300))  # quiénes aprobaron el texto (declarado al publicar)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    publicado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LgEvento(Base):
    """Evidencia mínima: quién (usuario u organización), qué versión, qué evento y cuándo. Sin IP,
    sin contenido de expedientes y sin datos que no hagan falta para probar la aceptación."""
    __tablename__ = "lg_eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int | None] = mapped_column(ForeignKey("lg_versiones.id"), index=True)
    documento: Mapped[str] = mapped_column(String(40), index=True)
    evento: Mapped[str] = mapped_column(String(30))  # aceptacion | lectura | marketing_otorgado | marketing_revocado | aviso_mostrado
    contexto: Mapped[str] = mapped_column(String(30))  # inicio_sesion | perfil | organizacion | formulario_informes
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    organizacion_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    solicitud_id: Mapped[int | None] = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class LgConfig(Base):
    """Datos de contacto de privacidad que muestra el Centro Legal (una sola fila)."""
    __tablename__ = "lg_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    correo_privacidad: Mapped[str | None] = mapped_column(String(254))
    responsable_datos: Mapped[str | None] = mapped_column(String(200))  # persona o departamento de datos personales
    marketing_habilitado: Mapped[bool] = mapped_column(Boolean, default=False)  # solo si Nomira hace marketing y el aviso lo prevé
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class LgSolicitud(Base):
    """Solicitud de derechos ARCO (o revocación / limitación). Nunca se marca atendida sola."""
    __tablename__ = "lg_solicitudes"
    id: Mapped[int] = mapped_column(primary_key=True)
    folio: Mapped[str] = mapped_column(String(20), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))  # acceso | rectificacion | cancelacion | oposicion | revocacion | limitacion
    relacion: Mapped[str] = mapped_column(String(20))  # usuario | cliente_despacho | prospecto | otro
    despacho: Mapped[str | None] = mapped_column(String(200))
    nombre: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    descripcion: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(25), default="recibida")
    recibida_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)
    vence_en: Mapped[date | None] = mapped_column(Date)  # referencia: 20 días hábiles (sin contar días festivos)
    atendida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class LgSolicitudNota(Base):
    __tablename__ = "lg_solicitud_notas"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("lg_solicitudes.id", ondelete="CASCADE"), index=True)
    estado: Mapped[str] = mapped_column(String(25))
    nota: Mapped[str | None] = mapped_column(Text)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# ---------------------------------------------------------------- Comercial (solo superadministrador)

class CmConfig(Base):
    """Datos comerciales de Nomira (una sola fila). Nada aquí se inventa: lo vacío no se muestra."""
    __tablename__ = "cm_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_comercial: Mapped[str] = mapped_column(String(120), default="Nomira")
    razon_social: Mapped[str | None] = mapped_column(String(200))
    rfc: Mapped[str | None] = mapped_column(String(13))
    domicilio: Mapped[str | None] = mapped_column(String(400))
    correo_ventas: Mapped[str | None] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(40))
    sitio_web: Mapped[str | None] = mapped_column(String(200))
    iva_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("16"))
    vigencia_dias: Mapped[int] = mapped_column(Integer, default=15)
    descuento_maximo_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20"))
    periodicidades: Mapped[list | None] = mapped_column(JSON)  # claves habilitadas: mensual | semestral | anual
    condiciones: Mapped[str | None] = mapped_column(Text)  # condiciones comerciales generales
    instrucciones_contratar: Mapped[str | None] = mapped_column(Text)
    notas_pie: Mapped[str | None] = mapped_column(Text)
    mb_promedio_por_asunto: Mapped[int | None] = mapped_column(Integer)  # solo referencia; vacío = no se estima
    asunto_correo: Mapped[str | None] = mapped_column(String(200))
    mensaje_presentacion: Mapped[str | None] = mapped_column(Text)
    aceptacion_en_linea: Mapped[bool] = mapped_column(Boolean, default=True)
    registro_prueba: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")  # registro en línea con prueba gratis
    precios_publicos: Mapped[str] = mapped_column(String(10), default="ocultos")  # ocultos | desde
    pago_tarjeta: Mapped[bool] = mapped_column(Boolean, default=False)  # solo funciona si Stripe está conectado
    spei_habilitado: Mapped[bool] = mapped_column(Boolean, default=False)
    spei_banco: Mapped[str | None] = mapped_column(String(80))
    spei_titular: Mapped[str | None] = mapped_column(String(200))
    spei_clabe: Mapped[str | None] = mapped_column(String(18))
    spei_instrucciones: Mapped[str | None] = mapped_column(Text)
    otro_habilitado: Mapped[bool] = mapped_column(Boolean, default=False)
    otro_nombre: Mapped[str | None] = mapped_column(String(80))
    otro_instrucciones: Mapped[str | None] = mapped_column(Text)
    # Costo del almacenamiento del proveedor (Render cobra el disco por GB al mes, en dólares).
    costo_gb_usd: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.25"), server_default="0.25")
    tipo_cambio: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("19"), server_default="19")
    margen_almacenamiento_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("150"), server_default="150")
    disco_gb: Mapped[int] = mapped_column(Integer, default=5, server_default="5")  # tamaño actual del disco en Render
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CmPaquete(Base):
    __tablename__ = "cm_paquetes"
    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    descripcion: Mapped[str | None] = mapped_column(String(500))
    precio_mensual: Mapped[Decimal] = mapped_column(DINERO)  # antes de IVA
    modulos_incluidos: Mapped[int] = mapped_column(Integer)  # cuántos módulos entran en el precio
    usuarios: Mapped[int] = mapped_column(Integer)  # usuarios internos (los clientes del portal no cuentan)
    almacenamiento_gb: Mapped[int] = mapped_column(Integer)
    ciclo: Mapped[str] = mapped_column(String(15), default="mensual")
    iva_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # vacío = el de la configuración
    estado: Mapped[str] = mapped_column(String(12), default="activo")  # activo | inactivo | archivado
    orden: Mapped[int] = mapped_column(Integer, default=0)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class CmPrecio(Base):
    """Precios de extras: módulos adicionales, usuario adicional, bloque de almacenamiento."""
    __tablename__ = "cm_precios"
    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(40), unique=True)  # modulo:nomina | usuario | almacenamiento
    nombre: Mapped[str] = mapped_column(String(120))
    precio_mensual: Mapped[Decimal] = mapped_column(DINERO)
    unidad_gb: Mapped[int | None] = mapped_column(Integer)  # solo almacenamiento: GB por bloque
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class CmCambioPrecio(Base):
    __tablename__ = "cm_cambios_precio"
    id: Mapped[int] = mapped_column(primary_key=True)
    entidad: Mapped[str] = mapped_column(String(15))  # paquete | precio
    entidad_id: Mapped[int] = mapped_column(Integer, index=True)
    campo: Mapped[str] = mapped_column(String(40))
    antes: Mapped[str | None] = mapped_column(String(200))
    despues: Mapped[str | None] = mapped_column(String(200))
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class CmCotizacion(Base):
    __tablename__ = "cm_cotizaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    folio: Mapped[str] = mapped_column(String(30), unique=True)
    # borrador | revision | enviada | vista | aceptada | pendiente_pago | pagada | vencida | cancelada
    estado: Mapped[str] = mapped_column(String(20), default="borrador", index=True)
    contacto: Mapped[str] = mapped_column(String(200))
    despacho: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(40))
    pais: Mapped[str] = mapped_column(String(2), default="MX")
    moneda: Mapped[str] = mapped_column(String(3), default="MXN")
    necesidad: Mapped[str | None] = mapped_column(String(1000))  # se muestra al cliente
    notas_internas: Mapped[str | None] = mapped_column(Text)  # NUNCA sale al cliente
    version_actual: Mapped[int] = mapped_column(Integer, default=1)
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Enlace del cliente: se busca por huella; se guarda cifrado solo para volver a mostrarlo al panel.
    enlace_huella: Mapped[str | None] = mapped_column(String(64), unique=True)
    enlace_cifrado: Mapped[str | None] = mapped_column(Text)
    enlace_vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enlace_revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organizacion_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id", ondelete="SET NULL"), index=True)
    oportunidad_id: Mapped[int | None] = mapped_column(ForeignKey("vt_oportunidades.id", ondelete="SET NULL"), index=True)  # Ventas
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vista_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aceptada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pagada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    convertida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CmVersion(Base):
    """Versión de una cotización. Al enviarse queda congelada: editarla crea la siguiente."""
    __tablename__ = "cm_versiones"
    __table_args__ = (UniqueConstraint("cotizacion_id", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cotizacion_id: Mapped[int] = mapped_column(ForeignKey("cm_cotizaciones.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    entrada: Mapped[dict] = mapped_column(JSON)  # lo que capturó el administrador
    calculo: Mapped[dict] = mapped_column(JSON)  # desglose calculado en el servidor (precios congelados)
    nomira: Mapped[dict | None] = mapped_column(JSON)  # datos comerciales y formas de pago al enviarse
    subtotal: Mapped[Decimal] = mapped_column(DINERO)
    descuento: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    iva: Mapped[Decimal] = mapped_column(DINERO)
    total: Mapped[Decimal] = mapped_column(DINERO)
    cambios: Mapped[list | None] = mapped_column(JSON)  # qué cambió respecto a la versión anterior
    huella: Mapped[str | None] = mapped_column(String(64))  # SHA-256 del contenido enviado
    preparada_por: Mapped[str | None] = mapped_column(String(200))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CmEvento(Base):
    __tablename__ = "cm_eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    cotizacion_id: Mapped[int] = mapped_column(ForeignKey("cm_cotizaciones.id", ondelete="CASCADE"), index=True)
    version: Mapped[int | None] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(30), index=True)
    actor: Mapped[str] = mapped_column(String(20))  # admin | cliente | stripe | sistema
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    detalle: Mapped[dict | None] = mapped_column(JSON)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class CmPago(Base):
    __tablename__ = "cm_pagos"
    id: Mapped[int] = mapped_column(primary_key=True)
    cotizacion_id: Mapped[int] = mapped_column(ForeignKey("cm_cotizaciones.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    metodo: Mapped[str] = mapped_column(String(15))  # tarjeta | spei | otro
    estado: Mapped[str] = mapped_column(String(15))  # iniciado | confirmado
    monto: Mapped[Decimal | None] = mapped_column(DINERO)
    referencia: Mapped[str | None] = mapped_column(String(120))
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    stripe_sesion: Mapped[str | None] = mapped_column(String(120), unique=True)
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CmCupon(Base):
    """Código de descuento (p. ej. BLACKDAY2026) que se aplica a una cotización, en el panel o en la propuesta del cliente."""
    __tablename__ = "cm_cupones"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)  # MAYÚSCULAS, sin espacios
    descripcion: Mapped[str | None] = mapped_column(String(300))  # interna: campaña, motivo
    tipo: Mapped[str] = mapped_column(String(12))  # porcentaje | monto
    valor: Mapped[Decimal] = mapped_column(DINERO)
    aplica_a: Mapped[str] = mapped_column(String(12), default="todo")  # todo | recurrente (solo la suscripción, no servicios ni cursos)
    inicia_en: Mapped[date | None] = mapped_column(Date)
    vence_en: Mapped[date | None] = mapped_column(Date)  # último día válido
    usos_maximos: Mapped[int | None] = mapped_column(Integer)  # vacío = sin límite
    usos: Mapped[int] = mapped_column(Integer, default=0)  # cotizaciones PAGADAS con el cupón
    minimo: Mapped[Decimal | None] = mapped_column(DINERO)  # subtotal mínimo antes de IVA
    estado: Mapped[str] = mapped_column(String(12), default="activo")  # activo | suspendido
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CmEventoStripe(Base):
    """Eventos de Stripe ya procesados: el mismo evento nunca se aplica dos veces."""
    __tablename__ = "cm_eventos_stripe"
    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[str] = mapped_column(String(120), unique=True)
    tipo: Mapped[str] = mapped_column(String(80))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class CmAsignacion(Base):
    """Paquete asignado a una organización. Vencer o cambiar de paquete nunca borra datos."""
    __tablename__ = "cm_asignaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    cotizacion_id: Mapped[int | None] = mapped_column(ForeignKey("cm_cotizaciones.id", ondelete="SET NULL"))
    periodo_id: Mapped[int | None] = mapped_column(ForeignKey("periodos_suscripcion.id", ondelete="SET NULL"))
    paquete: Mapped[str] = mapped_column(String(80))
    modulos: Mapped[list] = mapped_column(JSON)
    usuarios: Mapped[int] = mapped_column(Integer)
    almacenamiento_gb: Mapped[int] = mapped_column(Integer)
    periodicidad: Mapped[str] = mapped_column(String(15))
    monto: Mapped[Decimal] = mapped_column(DINERO)
    inicio: Mapped[date] = mapped_column(Date)
    renovacion: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), default="activa")  # activa | impago | vencida | cancelada
    origen: Mapped[str] = mapped_column(String(15))  # pago | promocional
    motivo: Mapped[str | None] = mapped_column(String(300))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# ================================================================== Nomira Agenda Jurídica

class AgConfig(Base):
    """Ajustes de la agenda por despacho (una fila por organización)."""
    __tablename__ = "ag_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), unique=True)
    alertas_plazo: Mapped[list | None] = mapped_column(JSON)  # días antes: [5, 3, 1, 0]
    alertas_audiencia: Mapped[list | None] = mapped_column(JSON)  # [7, 1, 0]
    escalar_a_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))  # vacío = administradores
    resumen_diario: Mapped[bool] = mapped_column(Boolean, default=True)
    hora_resumen: Mapped[int] = mapped_column(Integer, default=7)  # hora local (Ciudad de México)
    calendario_id: Mapped[int | None] = mapped_column(ForeignKey("ag_calendarios.id", ondelete="SET NULL"))  # por defecto
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgCalendario(Base):
    """Calendario de días hábiles de un tribunal o autoridad, capturado por el despacho."""
    __tablename__ = "ag_calendarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    jurisdiccion: Mapped[str] = mapped_column(String(20), default="federal")  # federal | estatal
    entidad: Mapped[str | None] = mapped_column(String(40))  # estado, si es estatal
    descripcion: Mapped[str | None] = mapped_column(String(500))
    fuente: Mapped[str | None] = mapped_column(String(500))  # acuerdo o circular de donde salen los días
    dias_semana_inhabiles: Mapped[list | None] = mapped_column(JSON)  # 0=lunes … 6=domingo; por defecto [5, 6]
    incluir_descanso_lft: Mapped[bool] = mapped_column(Boolean, default=True)  # días de descanso obligatorio (art. 74 LFT)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgDia(Base):
    __tablename__ = "ag_dias"
    __table_args__ = (UniqueConstraint("calendario_id", "fecha"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    calendario_id: Mapped[int] = mapped_column(ForeignKey("ag_calendarios.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    tipo: Mapped[str] = mapped_column(String(10), default="inhabil")  # inhabil | habil (habilitado de forma excepcional)
    motivo: Mapped[str] = mapped_column(String(200))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))


class AgAsunto(Base):
    """Juicio o procedimiento que se sigue en la agenda."""
    __tablename__ = "ag_asuntos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))  # p. ej. «Pérez vs. Empresa X»
    numero: Mapped[str | None] = mapped_column(String(80))  # número de expediente o juicio
    cr_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cr_clientes.id", ondelete="SET NULL"), index=True)  # directorio de Clientes
    jurisdiccion: Mapped[str] = mapped_column(String(20), default="federal")
    entidad: Mapped[str | None] = mapped_column(String(40))
    tribunal: Mapped[str | None] = mapped_column(String(200))
    materia: Mapped[str] = mapped_column(String(30))
    calendario_id: Mapped[int | None] = mapped_column(ForeignKey("ag_calendarios.id", ondelete="SET NULL"))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    expediente_id: Mapped[int | None] = mapped_column(ForeignKey("expedientes.id", ondelete="SET NULL"))
    ev_asunto_id: Mapped[int | None] = mapped_column(ForeignKey("ev_asuntos.id", ondelete="SET NULL"))
    notas: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(12), default="activo")  # activo | concluido | archivado
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgActuacion(Base):
    """Lo que pasó en el asunto: acuerdos, notificaciones, promociones, audiencias celebradas."""
    __tablename__ = "ag_actuaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    asunto_id: Mapped[int] = mapped_column(ForeignKey("ag_asuntos.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    tipo: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(String(1000))
    notificada_en: Mapped[date | None] = mapped_column(Date)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AgPlantilla(Base):
    """Plazos frecuentes que el propio despacho define (Nomira no precarga plazos legales)."""
    __tablename__ = "ag_plantillas"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    materia: Mapped[str | None] = mapped_column(String(30))
    dias: Mapped[int] = mapped_column(Integer)
    tipo_dias: Mapped[str] = mapped_column(String(10), default="habiles")  # habiles | naturales
    surte_efectos: Mapped[str] = mapped_column(String(25))  # mismo_dia | dia_habil_siguiente
    fundamento: Mapped[str | None] = mapped_column(String(500))
    alertas: Mapped[list | None] = mapped_column(JSON)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class AgEvento(Base):
    """Plazo, audiencia o actividad con responsable y alertas."""
    __tablename__ = "ag_eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    asunto_id: Mapped[int | None] = mapped_column(ForeignKey("ag_asuntos.id", ondelete="CASCADE"), index=True)
    actuacion_id: Mapped[int | None] = mapped_column(ForeignKey("ag_actuaciones.id", ondelete="SET NULL"))
    tipo: Mapped[str] = mapped_column(String(15))  # plazo | audiencia | actividad
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[date] = mapped_column(Date, index=True)  # vencimiento del plazo o día de la audiencia/actividad
    hora: Mapped[str | None] = mapped_column(String(5))  # HH:MM
    duracion_min: Mapped[int | None] = mapped_column(Integer)
    lugar: Mapped[str | None] = mapped_column(String(300))
    enlace: Mapped[str | None] = mapped_column(String(500))  # Zoom, Meet, Teams…
    prioridad: Mapped[str] = mapped_column(String(10), default="normal")  # normal | alta | critica
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    apoyo_ids: Mapped[list | None] = mapped_column(JSON)
    alertas: Mapped[list | None] = mapped_column(JSON)  # días antes
    calculo: Mapped[dict | None] = mapped_column(JSON)  # cálculo asistido con su desglose
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    validado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")  # pendiente | cumplido | cancelado
    cumplido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cumplido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    nota_cierre: Mapped[str | None] = mapped_column(String(1000))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgPreferencia(Base):
    __tablename__ = "ag_preferencias"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True)
    resumen_diario: Mapped[bool] = mapped_column(Boolean, default=True)
    alertas_correo: Mapped[bool] = mapped_column(Boolean, default=True)
    feed_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)  # enlace para Google/Outlook
    feed_detalle: Mapped[str] = mapped_column(String(10), default="reservado")  # reservado | completo
    feed_creado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgAviso(Base):
    """Aviso ya generado (evita repetirlo). El correo es opcional; el aviso también se ve en Nomira."""
    __tablename__ = "ag_avisos"
    __table_args__ = (UniqueConstraint("evento_id", "usuario_id", "clave", "fecha_evento"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("ag_eventos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    clave: Mapped[str] = mapped_column(String(20))  # d5 | d3 | d1 | d0 | escalado | vencido
    nivel: Mapped[str] = mapped_column(String(15))  # anticipado | hoy | escalado | vencido
    fecha_evento: Mapped[date] = mapped_column(Date)
    correo: Mapped[bool] = mapped_column(Boolean, default=False)
    leido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AgVigilancia(Base):
    """Expediente que Nomira revisa en los estrados digitales de un tribunal para avisar cuando hay publicación."""
    __tablename__ = "ag_vigilancias"
    __table_args__ = (UniqueConstraint("asunto_id", "fuente"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    asunto_id: Mapped[int] = mapped_column(ForeignKey("ag_asuntos.id", ondelete="CASCADE"), index=True)
    fuente: Mapped[str] = mapped_column(String(30), default="trijaem")  # tribunal / sistema de estrados
    expediente: Mapped[str] = mapped_column(String(80))  # como lo publica el tribunal, p. ej. 1234/2026
    sala: Mapped[str | None] = mapped_column(String(120))
    id_sala: Mapped[str | None] = mapped_column(String(10))  # clave de la sala en el sistema del tribunal
    circuito: Mapped[str | None] = mapped_column(String(10))  # PJF: circuito judicial (clave de la consulta oficial)
    promociones: Mapped[list | None] = mapped_column(JSON)  # números de promoción presentados que se quieren seguir
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    ultima_revision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente | ok | error | sin_conexion
    ultimo_error: Mapped[str | None] = mapped_column(String(300))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class AgPublicacion(Base):
    """Publicación encontrada (o registrada a mano) en estrados para un expediente vigilado."""
    __tablename__ = "ag_publicaciones"
    __table_args__ = (UniqueConstraint("vigilancia_id", "huella"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    vigilancia_id: Mapped[int] = mapped_column(ForeignKey("ag_vigilancias.id", ondelete="CASCADE"), index=True)
    huella: Mapped[str] = mapped_column(String(64))
    fecha_publicacion: Mapped[date] = mapped_column(Date)
    sala: Mapped[str | None] = mapped_column(String(120))
    tipo: Mapped[str | None] = mapped_column(String(80))  # acuerdo, sentencia, notificación…
    fecha_acuerdo: Mapped[date | None] = mapped_column(Date)
    promocion: Mapped[str | None] = mapped_column(String(30))  # número de promoción al que responde el acuerdo
    descripcion: Mapped[str] = mapped_column(String(2000))
    enlace: Mapped[str | None] = mapped_column(String(500))
    origen: Mapped[str] = mapped_column(String(12), default="automatica")  # automatica | manual
    actuacion_id: Mapped[int | None] = mapped_column(ForeignKey("ag_actuaciones.id", ondelete="SET NULL"))
    vista_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    vista_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encontrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# ---------------------------------------------------------------------------
# Clientes del despacho (mini CRM): directorio único que usan todos los módulos, sus documentos y su cobranza.
# Incluido en todos los planes. CURP cifrada como en AFORE.

class CrCliente(Base):
    __tablename__ = "cr_clientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(10), default="fisica")  # fisica | moral
    nombre: Mapped[str] = mapped_column(String(250))  # nombre completo o razón social
    rfc: Mapped[str | None] = mapped_column(String(13), index=True)
    curp_cifrado: Mapped[str | None] = mapped_column(Text)
    curp_pista: Mapped[str | None] = mapped_column(String(12))
    email: Mapped[str | None] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(20))
    domicilio: Mapped[str | None] = mapped_column(String(500))
    codigo_postal: Mapped[str | None] = mapped_column(String(5))
    regimen_fiscal: Mapped[str | None] = mapped_column(String(200))
    contacto: Mapped[str | None] = mapped_column(String(200))  # persona de contacto (personas morales)
    notas: Mapped[str | None] = mapped_column(Text)
    etiquetas: Mapped[list | None] = mapped_column(JSON)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    estado: Mapped[str] = mapped_column(String(10), default="activo")  # activo | inactivo
    origen: Mapped[str] = mapped_column(String(12), default="manual")  # manual | constancia | excel | leads | modulos
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class CrDocumento(Base):
    """Documento del cliente (identificación, constancia fiscal, contrato…). El archivo vive en el almacén del despacho."""
    __tablename__ = "cr_documentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cr_clientes.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="otro")  # identificacion | constancia | domicilio | contrato | poder | otro
    nombre: Mapped[str] = mapped_column(String(200))
    archivo: Mapped[str] = mapped_column(String(300))  # ruta relativa dentro del almacén
    tamano: Mapped[int] = mapped_column(BigInteger, default=0)
    mime: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    sha256: Mapped[str] = mapped_column(String(64))
    subido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class CrCargo(Base):
    """Honorario o cargo al cliente (pago único, parcialidad o mensualidad de una iguala)."""
    __tablename__ = "cr_cargos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cr_clientes.id", ondelete="CASCADE"), index=True)
    concepto: Mapped[str] = mapped_column(String(250))
    monto: Mapped[Decimal] = mapped_column(DINERO)
    fecha: Mapped[date] = mapped_column(Date)
    vence: Mapped[date] = mapped_column(Date, index=True)
    relacionado: Mapped[dict | None] = mapped_column(JSON)  # {"modulo": "agenda", "id": 3, "titulo": "..."}
    grupo: Mapped[str | None] = mapped_column(String(36))  # mensualidades creadas juntas (iguala)
    cancelado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(300))
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class CrPago(Base):
    """Pago recibido. Nunca se borra: se cancela con motivo. Sin cargo indicado se aplica a lo más antiguo."""
    __tablename__ = "cr_pagos"
    __table_args__ = (UniqueConstraint("organizacion_id", "folio"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cr_clientes.id", ondelete="CASCADE"), index=True)
    cargo_id: Mapped[int | None] = mapped_column(ForeignKey("cr_cargos.id", ondelete="SET NULL"))
    folio: Mapped[int] = mapped_column(Integer)
    monto: Mapped[Decimal] = mapped_column(DINERO)
    fecha: Mapped[date] = mapped_column(Date)
    metodo: Mapped[str] = mapped_column(String(15), default="transferencia")  # transferencia | efectivo | tarjeta | cheque | deposito | otro
    referencia: Mapped[str | None] = mapped_column(String(120))
    nota: Mapped[str | None] = mapped_column(String(500))
    cancelado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(300))
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# ---------------------------------------------------------------------------
# Ventas de Nomira (CRM interno del panel de la plataforma): campañas, contactos, oportunidades y actividades.
# Lo usan los empleados de Nomira. Son prospectos de Nomira: nunca datos de los expedientes de los despachos.

class VtCampana(Base):
    __tablename__ = "vt_campanas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    canal: Mapped[str] = mapped_column(String(20), default="otro")  # facebook | google | linkedin | correo | evento | referidos | sitio | otro
    estado: Mapped[str] = mapped_column(String(12), default="activa")  # activa | pausada | terminada
    inicio: Mapped[date | None] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    presupuesto: Mapped[Decimal | None] = mapped_column(DINERO)
    utm_campaign: Mapped[str | None] = mapped_column(String(120))
    notas: Mapped[str | None] = mapped_column(Text)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class VtContacto(Base):
    __tablename__ = "vt_contactos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    despacho: Mapped[str | None] = mapped_column(String(200))
    cargo: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(254), index=True)
    telefono: Mapped[str | None] = mapped_column(String(40))
    ciudad: Mapped[str | None] = mapped_column(String(120))
    entidad: Mapped[str | None] = mapped_column(String(40))
    abogados: Mapped[int | None] = mapped_column(Integer)  # tamaño del despacho
    especialidad: Mapped[str | None] = mapped_column(String(160))
    origen: Mapped[str] = mapped_column(String(20), default="otro")  # sitio | campana | referido | evento | prospeccion | redes | otro
    campana_id: Mapped[int | None] = mapped_column(ForeignKey("vt_campanas.id", ondelete="SET NULL"), index=True)
    propietario_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"), index=True)
    organizacion_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id", ondelete="SET NULL"))  # ya es cliente
    etiquetas: Mapped[list | None] = mapped_column(JSON)
    notas: Mapped[str | None] = mapped_column(Text)
    no_contactar: Mapped[bool] = mapped_column(Boolean, default=False)  # pidió no ser contactado
    # Calificación: mql = lead (aún sin contacto real) · sql = contacto (al menos una llamada efectiva o aceptó por correo) · descartado
    fase: Mapped[str] = mapped_column(String(12), default="mql", server_default="sql", index=True)
    calificacion: Mapped[str | None] = mapped_column(String(15))  # llamada | respuesta | reunion | demo | manual
    calificado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calificado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    motivo_descarte: Mapped[str | None] = mapped_column(String(30))
    solicitud_id: Mapped[int | None] = mapped_column(ForeignKey("solicitudes.id", ondelete="SET NULL"))  # llegó por el sitio
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class VtOportunidad(Base):
    """Posible venta a un contacto, desde que llega hasta que se gana o se pierde."""
    __tablename__ = "vt_oportunidades"
    id: Mapped[int] = mapped_column(primary_key=True)
    contacto_id: Mapped[int] = mapped_column(ForeignKey("vt_contactos.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    etapa: Mapped[str] = mapped_column(String(15), default="contactado", index=True)
    valor_mensual: Mapped[Decimal | None] = mapped_column(DINERO)  # estimado, antes de IVA
    paquete_interes: Mapped[str | None] = mapped_column(String(80))
    modulos_interes: Mapped[list | None] = mapped_column(JSON)
    cierre_estimado: Mapped[date | None] = mapped_column(Date)
    origen: Mapped[str] = mapped_column(String(20), default="otro")
    campana_id: Mapped[int | None] = mapped_column(ForeignKey("vt_campanas.id", ondelete="SET NULL"), index=True)
    solicitud_id: Mapped[int | None] = mapped_column(ForeignKey("solicitudes.id", ondelete="SET NULL"), unique=True)
    propietario_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"), index=True)
    motivo_perdida: Mapped[str | None] = mapped_column(String(30))
    nota_cierre: Mapped[str | None] = mapped_column(String(500))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organizacion_id: Mapped[int | None] = mapped_column(ForeignKey("organizaciones.id", ondelete="SET NULL"))
    ultima_actividad_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class VtActividad(Base):
    """Historial (llamadas, correos, reuniones, notas) y tareas por hacer con fecha."""
    __tablename__ = "vt_actividades"
    id: Mapped[int] = mapped_column(primary_key=True)
    contacto_id: Mapped[int] = mapped_column(ForeignKey("vt_contactos.id", ondelete="CASCADE"), index=True)
    oportunidad_id: Mapped[int | None] = mapped_column(ForeignKey("vt_oportunidades.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(15))  # llamada | correo | whatsapp | reunion | demo | nota | tarea | sistema
    titulo: Mapped[str] = mapped_column(String(200))
    detalle: Mapped[str | None] = mapped_column(Text)
    vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)  # con fecha = tarea por hacer
    completada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str | None] = mapped_column(String(500))
    asignado_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"), index=True)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("administradores_plataforma.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


# ---------------------------------------------------------------------------
# Nomira Escrituración (módulo para notarías): expediente por acto, avance por etapas visible para el cliente,
# requisitos con vigencia y semáforo «listo para firmar», y portal de seguimiento por enlace.

class EsExpediente(Base):
    __tablename__ = "es_expedientes"
    __table_args__ = (UniqueConstraint("organizacion_id", "folio"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    folio: Mapped[str] = mapped_column(String(20))  # interno de la notaría, p. ej. ESC-2026-0007
    acto: Mapped[str] = mapped_column(String(30))  # compraventa | compraventa_credito | donacion | adjudicacion | testamento | poder | sociedad | cancelacion_hipoteca | otro
    titulo: Mapped[str] = mapped_column(String(200))
    inmueble: Mapped[str | None] = mapped_column(String(500))  # ubicación
    folio_real: Mapped[str | None] = mapped_column(String(60))
    clave_catastral: Mapped[str | None] = mapped_column(String(60))
    valor_operacion: Mapped[Decimal | None] = mapped_column(DINERO)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    estado: Mapped[str] = mapped_column(String(12), default="abierto", index=True)  # abierto | concluido | cancelado
    cita_firma: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cita_lugar: Mapped[str | None] = mapped_column(String(300))
    numero_escritura: Mapped[str | None] = mapped_column(String(30))
    volumen: Mapped[str | None] = mapped_column(String(30))
    folio_registro: Mapped[str | None] = mapped_column(String(60))  # número de entrada en el Registro Público
    mensaje_cliente: Mapped[str | None] = mapped_column(String(1000))  # aviso visible en el portal
    notas: Mapped[str | None] = mapped_column(Text)  # internas, nunca al portal
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class EsParte(Base):
    __tablename__ = "es_partes"
    id: Mapped[int] = mapped_column(primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("es_expedientes.id", ondelete="CASCADE"), index=True)
    rol: Mapped[str] = mapped_column(String(20))  # comprador | vendedor | donante | donatario | testador | poderdante | apoderado | acreditante | otro
    cr_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cr_clientes.id", ondelete="SET NULL"))
    nombre: Mapped[str] = mapped_column(String(250))
    tipo: Mapped[str] = mapped_column(String(10), default="fisica")  # fisica | moral
    email: Mapped[str | None] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(20))
    casado: Mapped[bool] = mapped_column(Boolean, default=False)


class EsHito(Base):
    """Etapa del trámite. Las visibles salen en el portal del cliente con su fecha y nota pública."""
    __tablename__ = "es_hitos"
    id: Mapped[int] = mapped_column(primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("es_expedientes.id", ondelete="CASCADE"), index=True)
    clave: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(120))
    orden: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")  # pendiente | en_proceso | observado | hecho | no_aplica
    fecha: Mapped[date | None] = mapped_column(Date)
    nota_publica: Mapped[str | None] = mapped_column(String(500))
    visible_cliente: Mapped[bool] = mapped_column(Boolean, default=True)
    actualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EsRequisito(Base):
    """Documento que se necesita para firmar. Con vigencia: vence N días después de su fecha de expedición."""
    __tablename__ = "es_requisitos"
    id: Mapped[int] = mapped_column(primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("es_expedientes.id", ondelete="CASCADE"), index=True)
    parte_id: Mapped[int | None] = mapped_column(ForeignKey("es_partes.id", ondelete="CASCADE"), index=True)  # vacío = del inmueble u operación
    clave: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(160))
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=True)
    vigencia_dias: Mapped[int | None] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")  # pendiente | recibido | validado | rechazado | no_aplica
    expedido_en: Mapped[date | None] = mapped_column(Date)
    vence_en: Mapped[date | None] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(String(500))  # visible para el cliente si se rechaza (qué corregir)
    archivo: Mapped[str | None] = mapped_column(String(300))
    archivo_nombre: Mapped[str | None] = mapped_column(String(200))
    archivo_mime: Mapped[str | None] = mapped_column(String(100))
    origen: Mapped[str | None] = mapped_column(String(10))  # notaria | cliente
    recibido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    validado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EsAcceso(Base):
    """Enlace de seguimiento para una parte, la inmobiliaria o el banco. Solo se guarda la huella del token."""
    __tablename__ = "es_accesos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("es_expedientes.id", ondelete="CASCADE"), index=True)
    parte_id: Mapped[int | None] = mapped_column(ForeignKey("es_partes.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(15), default="parte")  # parte | inmobiliaria | banco | otro
    nombre: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254))
    avisar: Mapped[bool] = mapped_column(Boolean, default=True)  # correo cuando avanza el trámite
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_pista: Mapped[str] = mapped_column(String(8))
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visitas: Mapped[int] = mapped_column(Integer, default=0)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class LqCalculo(Base):
    """Cálculo de finiquito o liquidación (LFT) de una persona trabajadora; puede ligarse a un asunto de la Agenda."""
    __tablename__ = "lq_calculos"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    trabajador: Mapped[str] = mapped_column(String(200))
    patron: Mapped[str | None] = mapped_column(String(200))
    ag_asunto_id: Mapped[int | None] = mapped_column(ForeignKey("ag_asuntos.id", ondelete="SET NULL"), index=True)
    cr_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cr_clientes.id", ondelete="SET NULL"), index=True)
    causa: Mapped[str] = mapped_column(String(30))
    datos: Mapped[dict] = mapped_column(JSON)  # lo capturado, para volver a calcular
    resultado: Mapped[dict] = mapped_column(JSON)  # instantánea del último cálculo
    total: Mapped[Decimal] = mapped_column(DINERO)
    propuesta: Mapped[Decimal | None] = mapped_column(DINERO)  # monto que se propone en conciliación o convenio
    autorizado: Mapped[Decimal | None] = mapped_column(DINERO)  # monto que el cliente autorizó negociar
    notas: Mapped[str | None] = mapped_column(Text)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
