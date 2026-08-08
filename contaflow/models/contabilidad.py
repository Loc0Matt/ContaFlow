"""Plan de cuentas y comprobantes contables (libro diario)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean, Date, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from contaflow.models.base import (
    Base, EstadoComprobante, OrigenComprobante, TimestampMixin, TipoComprobante, TipoCuenta,
)


class Cuenta(Base):
    """Cuenta del plan de cuentas. Jerárquica por código (1, 1.1, 1.1.01...)."""

    __tablename__ = "cuenta"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_cuenta_codigo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(String(30), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoCuenta] = mapped_column(Enum(TipoCuenta))
    nivel: Mapped[int] = mapped_column(Integer, default=1)
    padre_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.id", ondelete="SET NULL"))
    #: Sólo las cuentas imputables reciben movimientos.
    imputable: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Fuerza a indicar la entidad (cliente/proveedor) en cada movimiento.
    requiere_auxiliar: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_centro_costo: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Marca cuentas de banco para la conciliación bancaria.
    es_banco: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Clasificación para el Estado de Situación Financiera.
    grupo: Mapped[str | None] = mapped_column(String(60))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    empresa: Mapped["Empresa"] = relationship(back_populates="cuentas")  # noqa: F821
    padre: Mapped["Cuenta | None"] = relationship(remote_side=[id])

    def __str__(self) -> str:
        return f"{self.codigo} {self.nombre}"


class Comprobante(Base, TimestampMixin):
    """Asiento contable. Cabecera del libro diario."""

    __tablename__ = "comprobante"
    __table_args__ = (
        UniqueConstraint("empresa_id", "tipo", "anio", "numero", name="uq_comprobante_num"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[TipoComprobante] = mapped_column(Enum(TipoComprobante))
    anio: Mapped[int] = mapped_column(Integer, index=True)
    numero: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    glosa: Mapped[str] = mapped_column(String(300))
    estado: Mapped[EstadoComprobante] = mapped_column(
        Enum(EstadoComprobante), default=EstadoComprobante.BORRADOR
    )
    origen: Mapped[OrigenComprobante] = mapped_column(
        Enum(OrigenComprobante), default=OrigenComprobante.MANUAL
    )
    #: Id del documento/liquidación/activo que generó el asiento automático.
    origen_id: Mapped[int | None] = mapped_column(Integer, index=True)
    total_debe: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_haber: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    observacion: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[str | None] = mapped_column(String(60))

    lineas: Mapped[list["Movimiento"]] = relationship(
        back_populates="comprobante",
        cascade="all, delete-orphan",
        order_by="Movimiento.orden",
    )

    @property
    def cuadrado(self) -> bool:
        return round(float(self.total_debe) - float(self.total_haber), 2) == 0

    @property
    def folio(self) -> str:
        return f"{self.tipo.value[:1]}-{self.anio}-{self.numero:05d}"


class Movimiento(Base):
    """Línea de un comprobante. Unidad mínima del libro mayor."""

    __tablename__ = "movimiento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comprobante_id: Mapped[int] = mapped_column(
        ForeignKey("comprobante.id", ondelete="CASCADE"), index=True
    )
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuenta.id"), index=True)
    glosa: Mapped[str | None] = mapped_column(String(300))
    debe: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    haber: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    centro_costo_id: Mapped[int | None] = mapped_column(
        ForeignKey("centro_costo.id", ondelete="SET NULL")
    )
    entidad_id: Mapped[int | None] = mapped_column(ForeignKey("entidad.id", ondelete="SET NULL"))
    documento_tipo: Mapped[str | None] = mapped_column(String(10))
    documento_folio: Mapped[str | None] = mapped_column(String(30))
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    #: Marca de conciliación bancaria.
    conciliado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_conciliacion: Mapped[date | None] = mapped_column(Date)

    comprobante: Mapped[Comprobante] = relationship(back_populates="lineas")
    cuenta: Mapped[Cuenta] = relationship()
    entidad: Mapped["Entidad | None"] = relationship()  # noqa: F821
    centro_costo: Mapped["CentroCosto | None"] = relationship()  # noqa: F821
