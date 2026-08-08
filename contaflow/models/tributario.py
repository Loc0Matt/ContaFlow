"""Documentos tributarios, honorarios y declaraciones (F29 / F22)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean, Date, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from contaflow.models.base import Base, ClaseDocumento, TimestampMixin, TipoCompra


class TipoDTE(Base):
    """Catálogo oficial de tipos de documento tributario del SII (global)."""

    __tablename__ = "tipo_dte"

    codigo: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    es_venta: Mapped[bool] = mapped_column(Boolean, default=False)
    es_compra: Mapped[bool] = mapped_column(Boolean, default=False)
    afecto_iva: Mapped[bool] = mapped_column(Boolean, default=True)
    #: 1 = suma, -1 = resta (notas de crédito).
    signo: Mapped[int] = mapped_column(Integer, default=1)
    electronico: Mapped[bool] = mapped_column(Boolean, default=True)

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nombre}"


class Documento(Base, TimestampMixin):
    """Factura, boleta, nota de crédito/débito emitida o recibida."""

    __tablename__ = "documento"
    __table_args__ = (
        UniqueConstraint("empresa_id", "clase", "tipo_dte", "folio", "entidad_rut",
                         name="uq_documento"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    clase: Mapped[ClaseDocumento] = mapped_column(Enum(ClaseDocumento), index=True)
    tipo_dte: Mapped[int] = mapped_column(ForeignKey("tipo_dte.codigo"))
    folio: Mapped[str] = mapped_column(String(30))
    fecha_emision: Mapped[date] = mapped_column(Date, index=True)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    #: Período tributario en que se declara (puede diferir de la emisión).
    periodo_anio: Mapped[int] = mapped_column(Integer, index=True)
    periodo_mes: Mapped[int] = mapped_column(Integer, index=True)

    entidad_id: Mapped[int | None] = mapped_column(ForeignKey("entidad.id", ondelete="SET NULL"))
    entidad_rut: Mapped[str] = mapped_column(String(12), index=True)
    entidad_nombre: Mapped[str] = mapped_column(String(200))

    neto: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    exento: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    iva: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    #: IVA de uso común y no recuperable (compras).
    iva_uso_comun: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    iva_no_recuperable: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    #: Impuestos adicionales: ILA, combustibles, lujo, etc.
    impuesto_adicional: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    tasa_impuesto_adicional: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    #: Retención (facturas de compra, cambio de sujeto).
    retencion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    tipo_compra: Mapped[TipoCompra] = mapped_column(Enum(TipoCompra), default=TipoCompra.DEL_GIRO)
    #: Referencia para notas de crédito/débito.
    ref_tipo_dte: Mapped[int | None] = mapped_column(Integer)
    ref_folio: Mapped[str | None] = mapped_column(String(30))
    ref_fecha: Mapped[date | None] = mapped_column(Date)
    ref_razon: Mapped[str | None] = mapped_column(String(200))

    anulado: Mapped[bool] = mapped_column(Boolean, default=False)
    pagado: Mapped[bool] = mapped_column(Boolean, default=False)
    observacion: Mapped[str | None] = mapped_column(Text)
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobante.id", ondelete="SET NULL")
    )

    tipo: Mapped[TipoDTE] = relationship()
    entidad: Mapped["Entidad | None"] = relationship()  # noqa: F821
    detalles: Mapped[list["DocumentoDetalle"]] = relationship(
        back_populates="documento", cascade="all, delete-orphan"
    )

    @property
    def signo(self) -> int:
        return self.tipo.signo if self.tipo else 1

    @property
    def iva_recuperable(self) -> float:
        """Parte del IVA que da derecho a crédito fiscal."""
        return float(self.iva)


class DocumentoDetalle(Base):
    __tablename__ = "documento_detalle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        ForeignKey("documento.id", ondelete="CASCADE"), index=True
    )
    descripcion: Mapped[str] = mapped_column(String(250))
    cantidad: Mapped[float] = mapped_column(Numeric(14, 3), default=1)
    precio_unitario: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    descuento: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    es_exento: Mapped[bool] = mapped_column(Boolean, default=False)
    total: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    cuenta_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.id", ondelete="SET NULL"))

    documento: Mapped[Documento] = relationship(back_populates="detalles")


class Honorario(Base, TimestampMixin):
    """Boleta de honorarios emitida o recibida (segunda categoría)."""

    __tablename__ = "honorario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    #: RECIBIDA = boleta de un tercero (retiene la empresa).
    #: EMITIDA  = boleta de honorarios propia (BTE) con retención del pagador.
    tipo: Mapped[str] = mapped_column(String(10), default="RECIBIDA")
    numero: Mapped[str] = mapped_column(String(30))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    periodo_anio: Mapped[int] = mapped_column(Integer, index=True)
    periodo_mes: Mapped[int] = mapped_column(Integer, index=True)
    entidad_id: Mapped[int | None] = mapped_column(ForeignKey("entidad.id", ondelete="SET NULL"))
    entidad_rut: Mapped[str] = mapped_column(String(12))
    entidad_nombre: Mapped[str] = mapped_column(String(200))
    bruto: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    tasa_retencion: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    retencion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    liquido: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    glosa: Mapped[str | None] = mapped_column(String(250))
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobante.id", ondelete="SET NULL")
    )


class Declaracion(Base, TimestampMixin):
    """Declaración generada (F29 mensual o F22 anual) con sus códigos."""

    __tablename__ = "declaracion"
    __table_args__ = (
        UniqueConstraint("empresa_id", "formulario", "anio", "mes", name="uq_declaracion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    formulario: Mapped[str] = mapped_column(String(10))   # F29 | F22 | F50
    anio: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, default=0)  # 0 para formularios anuales
    #: Diccionario {codigo: valor} serializado en JSON.
    codigos_json: Mapped[str] = mapped_column(Text, default="{}")
    total_a_pagar: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    remanente_siguiente: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    estado: Mapped[str] = mapped_column(String(20), default="BORRADOR")  # BORRADOR|DECLARADO
    observacion: Mapped[str | None] = mapped_column(Text)
