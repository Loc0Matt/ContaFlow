"""Empresas, usuarios, entidades (clientes/proveedores) y parámetros."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from contaflow.models.base import Base, EstadoPeriodo, RegimenTributario, TimestampMixin


class Empresa(Base, TimestampMixin):
    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rut: Mapped[str] = mapped_column(String(12), unique=True)
    razon_social: Mapped[str] = mapped_column(String(200))
    nombre_fantasia: Mapped[str | None] = mapped_column(String(200))
    giro: Mapped[str | None] = mapped_column(String(250))
    actividad_codigo: Mapped[str | None] = mapped_column(String(20))
    direccion: Mapped[str | None] = mapped_column(String(250))
    comuna: Mapped[str | None] = mapped_column(String(100))
    ciudad: Mapped[str | None] = mapped_column(String(100))
    telefono: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(150))
    regimen: Mapped[RegimenTributario] = mapped_column(
        Enum(RegimenTributario), default=RegimenTributario.ART14D3
    )
    representante_rut: Mapped[str | None] = mapped_column(String(12))
    representante_nombre: Mapped[str | None] = mapped_column(String(200))
    fecha_inicio_actividades: Mapped[date | None] = mapped_column(Date)
    #: Tasa de PPM vigente (porcentaje sobre ingresos brutos).
    tasa_ppm: Mapped[float] = mapped_column(Numeric(6, 3), default=0.25)
    contabilidad_completa: Mapped[bool] = mapped_column(Boolean, default=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    cuentas: Mapped[list["Cuenta"]] = relationship(  # noqa: F821
        back_populates="empresa", cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        return f"{self.rut} · {self.razon_social}"


class Usuario(Base, TimestampMixin):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Fuerza el cambio de contraseña antes de poder usar el resto del
    #: sistema — sembrado en True para el admin/admin inicial.
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime)


class Parametro(Base):
    """Clave/valor por empresa. `empresa_id = NULL` para parámetros globales."""

    __tablename__ = "parametro"
    __table_args__ = (UniqueConstraint("empresa_id", "clave", name="uq_parametro"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(
        ForeignKey("empresa.id", ondelete="CASCADE"), index=True
    )
    clave: Mapped[str] = mapped_column(String(80))
    valor: Mapped[str] = mapped_column(Text, default="")
    descripcion: Mapped[str | None] = mapped_column(String(250))


class CentroCosto(Base):
    __tablename__ = "centro_costo"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_cc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Entidad(Base, TimestampMixin):
    """Clientes, proveedores y terceros con los que se emiten documentos."""

    __tablename__ = "entidad"
    __table_args__ = (UniqueConstraint("empresa_id", "rut", name="uq_entidad_rut"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    rut: Mapped[str] = mapped_column(String(12), index=True)
    razon_social: Mapped[str] = mapped_column(String(200))
    giro: Mapped[str | None] = mapped_column(String(250))
    direccion: Mapped[str | None] = mapped_column(String(250))
    comuna: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(150))
    telefono: Mapped[str | None] = mapped_column(String(50))
    es_cliente: Mapped[bool] = mapped_column(Boolean, default=False)
    es_proveedor: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    def __str__(self) -> str:
        return f"{self.rut} · {self.razon_social}"


class Periodo(Base):
    """Control de apertura/cierre mensual. Impide alterar meses ya declarados."""

    __tablename__ = "periodo"
    __table_args__ = (UniqueConstraint("empresa_id", "anio", "mes", name="uq_periodo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    anio: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    estado: Mapped[EstadoPeriodo] = mapped_column(Enum(EstadoPeriodo), default=EstadoPeriodo.ABIERTO)
    observacion: Mapped[str | None] = mapped_column(String(250))


class Indicador(Base):
    """UF, UTM, UTA, IPC e ingreso mínimo. Carga manual (el sistema es offline)."""

    __tablename__ = "indicador"
    __table_args__ = (UniqueConstraint("anio", "mes", name="uq_indicador_periodo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    anio: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer)
    uf: Mapped[float] = mapped_column(Numeric(14, 4), default=0)      # UF último día del mes
    utm: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    uta: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    ipc: Mapped[float] = mapped_column(Numeric(8, 4), default=0)      # variación % del mes
    ingreso_minimo: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    dolar: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
