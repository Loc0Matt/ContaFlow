"""Base declarativa, mixins y enumeraciones del dominio."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EmpresaMixin:
    """Todo dato contable pertenece a una empresa (sistema multiempresa)."""

    @staticmethod
    def _fk():
        from sqlalchemy import ForeignKey

        return mapped_column(Integer, ForeignKey("empresa.id", ondelete="CASCADE"), index=True)


# --------------------------------------------------------------------------
# Enumeraciones
# --------------------------------------------------------------------------


class TipoCuenta(str, enum.Enum):
    ACTIVO = "ACTIVO"
    PASIVO = "PASIVO"
    PATRIMONIO = "PATRIMONIO"
    PERDIDA = "PERDIDA"
    GANANCIA = "GANANCIA"
    ORDEN = "ORDEN"

    @property
    def es_balance(self) -> bool:
        return self in (TipoCuenta.ACTIVO, TipoCuenta.PASIVO, TipoCuenta.PATRIMONIO)

    @property
    def es_resultado(self) -> bool:
        return self in (TipoCuenta.PERDIDA, TipoCuenta.GANANCIA)

    @property
    def naturaleza_deudora(self) -> bool:
        """Cuentas cuyo saldo normal está al debe."""
        return self in (TipoCuenta.ACTIVO, TipoCuenta.PERDIDA)


class TipoComprobante(str, enum.Enum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"
    TRASPASO = "TRASPASO"
    APERTURA = "APERTURA"
    CIERRE = "CIERRE"
    AJUSTE = "AJUSTE"


class EstadoComprobante(str, enum.Enum):
    BORRADOR = "BORRADOR"
    CONTABILIZADO = "CONTABILIZADO"
    ANULADO = "ANULADO"


class OrigenComprobante(str, enum.Enum):
    MANUAL = "MANUAL"
    VENTA = "VENTA"
    COMPRA = "COMPRA"
    HONORARIO = "HONORARIO"
    REMUNERACION = "REMUNERACION"
    DEPRECIACION = "DEPRECIACION"
    CIERRE = "CIERRE"


class ClaseDocumento(str, enum.Enum):
    VENTA = "VENTA"
    COMPRA = "COMPRA"


class TipoCompra(str, enum.Enum):
    """Clasificación exigida por el Registro de Compras del SII."""

    DEL_GIRO = "DEL_GIRO"
    ACTIVO_FIJO = "ACTIVO_FIJO"
    SUPERMERCADO = "SUPERMERCADO"
    IVA_USO_COMUN = "IVA_USO_COMUN"
    IVA_NO_RECUPERABLE = "IVA_NO_RECUPERABLE"


class RegimenTributario(str, enum.Enum):
    ART14A = "ART14A"           # Semi Integrado
    ART14D3 = "ART14D3"         # Pro Pyme General
    ART14D8 = "ART14D8"         # Pro Pyme Transparente
    RENTA_PRESUNTA = "RENTA_PRESUNTA"
    CONTRIBUYENTE_2A = "CONTRIBUYENTE_2A"  # Segunda categoría / honorarios

    @property
    def etiqueta(self) -> str:
        return {
            "ART14A": "14 A — Semi Integrado",
            "ART14D3": "14 D N°3 — Pro Pyme General",
            "ART14D8": "14 D N°8 — Pro Pyme Transparente",
            "RENTA_PRESUNTA": "Renta Presunta",
            "CONTRIBUYENTE_2A": "Segunda Categoría (Honorarios)",
        }[self.value]


class EstadoPeriodo(str, enum.Enum):
    ABIERTO = "ABIERTO"
    CERRADO = "CERRADO"


class TipoContrato(str, enum.Enum):
    INDEFINIDO = "INDEFINIDO"
    PLAZO_FIJO = "PLAZO_FIJO"
    OBRA_FAENA = "OBRA_FAENA"


class TipoSalud(str, enum.Enum):
    FONASA = "FONASA"
    ISAPRE = "ISAPRE"
