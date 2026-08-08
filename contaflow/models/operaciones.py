"""Activo fijo, depreciación y remuneraciones."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean, Date, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from contaflow.models.base import Base, TimestampMixin, TipoContrato, TipoSalud


# ---------------------------------------------------------------------------
# Activo fijo
# ---------------------------------------------------------------------------


class ActivoFijo(Base, TimestampMixin):
    __tablename__ = "activo_fijo"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_activo_codigo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str | None] = mapped_column(String(80))
    fecha_adquisicion: Mapped[date] = mapped_column(Date)
    valor_adquisicion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    valor_residual: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    #: Vida útil en meses según tabla del SII (Res. Ex. N°43 de 2002).
    vida_util_meses: Mapped[int] = mapped_column(Integer, default=36)
    #: Depreciación acelerada = vida útil normal / 3 (mínimo 1 año).
    usa_acelerada: Mapped[bool] = mapped_column(Boolean, default=False)

    cuenta_activo_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.id"))
    cuenta_depreciacion_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.id"))
    cuenta_gasto_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.id"))
    centro_costo_id: Mapped[int | None] = mapped_column(
        ForeignKey("centro_costo.id", ondelete="SET NULL")
    )
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("documento.id", ondelete="SET NULL"))

    dado_de_baja: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_baja: Mapped[date | None] = mapped_column(Date)
    valor_venta: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    observacion: Mapped[str | None] = mapped_column(Text)

    depreciaciones: Mapped[list["Depreciacion"]] = relationship(
        back_populates="activo", cascade="all, delete-orphan", order_by="Depreciacion.anio, Depreciacion.mes"
    )

    @property
    def vida_util_efectiva(self) -> int:
        if self.usa_acelerada:
            return max(12, self.vida_util_meses // 3)
        return self.vida_util_meses

    @property
    def depreciable(self) -> float:
        return float(self.valor_adquisicion) - float(self.valor_residual)

    @property
    def cuota_mensual(self) -> float:
        meses = self.vida_util_efectiva or 1
        return round(self.depreciable / meses, 2)


class Depreciacion(Base):
    __tablename__ = "depreciacion"
    __table_args__ = (UniqueConstraint("activo_id", "anio", "mes", name="uq_depreciacion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activo_id: Mapped[int] = mapped_column(
        ForeignKey("activo_fijo.id", ondelete="CASCADE"), index=True
    )
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    anio: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer)
    monto: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    acumulado: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    valor_libro: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobante.id", ondelete="SET NULL")
    )

    activo: Mapped[ActivoFijo] = relationship(back_populates="depreciaciones")


# ---------------------------------------------------------------------------
# Remuneraciones
# ---------------------------------------------------------------------------


class AFP(Base):
    __tablename__ = "afp"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)
    #: Tasa total de cotización obligatoria (10% + comisión), en porcentaje.
    tasa: Mapped[float] = mapped_column(Numeric(6, 3), default=11.44)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class Trabajador(Base, TimestampMixin):
    __tablename__ = "trabajador"
    __table_args__ = (UniqueConstraint("empresa_id", "rut", name="uq_trabajador_rut"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    rut: Mapped[str] = mapped_column(String(12))
    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str] = mapped_column(String(120))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    cargo: Mapped[str | None] = mapped_column(String(120))
    fecha_ingreso: Mapped[date] = mapped_column(Date)
    fecha_termino: Mapped[date | None] = mapped_column(Date)
    tipo_contrato: Mapped[TipoContrato] = mapped_column(
        Enum(TipoContrato), default=TipoContrato.INDEFINIDO
    )
    sueldo_base: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    #: Gratificación Art. 50 (25% con tope 4,75 IMM anual).
    gratificacion_legal: Mapped[bool] = mapped_column(Boolean, default=True)
    colacion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    movilizacion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    afp_id: Mapped[int | None] = mapped_column(ForeignKey("afp.id"))
    salud_tipo: Mapped[TipoSalud] = mapped_column(Enum(TipoSalud), default=TipoSalud.FONASA)
    isapre_nombre: Mapped[str | None] = mapped_column(String(80))
    #: Valor del plan pactado en UF (sólo Isapre).
    isapre_plan_uf: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    afecto_afc: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Jubilado que no cotiza en AFP.
    jubilado: Mapped[bool] = mapped_column(Boolean, default=False)
    cargas_familiares: Mapped[int] = mapped_column(Integer, default=0)
    asignacion_familiar_tramo: Mapped[str] = mapped_column(String(1), default="D")

    centro_costo_id: Mapped[int | None] = mapped_column(
        ForeignKey("centro_costo.id", ondelete="SET NULL")
    )
    banco: Mapped[str | None] = mapped_column(String(80))
    cuenta_banco: Mapped[str | None] = mapped_column(String(50))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    afp: Mapped["AFP | None"] = relationship()

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()


class Liquidacion(Base, TimestampMixin):
    """Liquidación de sueldo mensual."""

    __tablename__ = "liquidacion"
    __table_args__ = (
        UniqueConstraint("trabajador_id", "anio", "mes", name="uq_liquidacion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    trabajador_id: Mapped[int] = mapped_column(
        ForeignKey("trabajador.id", ondelete="CASCADE"), index=True
    )
    anio: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)
    dias_trabajados: Mapped[int] = mapped_column(Integer, default=30)

    # Haberes imponibles
    sueldo_base: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    gratificacion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    horas_extra: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bonos: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    comisiones: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_imponible: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Haberes no imponibles
    colacion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    movilizacion: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    asignacion_familiar: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    otros_no_imponibles: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_no_imponible: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_haberes: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Descuentos
    afp_tasa: Mapped[float] = mapped_column(Numeric(6, 3), default=0)
    afp_monto: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    salud_monto: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    salud_adicional: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    afc_monto: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    base_tributable: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    impuesto_unico: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    anticipos: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    otros_descuentos: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_descuentos: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    liquido: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    # Aportes del empleador
    sis_empleador: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    afc_empleador: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    mutual: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    costo_empresa: Mapped[float] = mapped_column(Numeric(18, 2), default=0)

    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobante.id", ondelete="SET NULL")
    )
    observacion: Mapped[str | None] = mapped_column(Text)

    trabajador: Mapped[Trabajador] = relationship()
