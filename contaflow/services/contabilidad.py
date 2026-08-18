"""Motor contable: creación de asientos, libro mayor y saldos."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from contaflow.models import (
    Comprobante, Cuenta, EstadoComprobante, EstadoPeriodo, Movimiento, OrigenComprobante,
    Periodo, TipoComprobante, TipoCuenta,
)
from contaflow.services.utils import pesos, rango_mes


class ErrorContable(Exception):
    """Regla de negocio contable incumplida."""


@contextmanager
def capturar_integridad(db: Session, mensaje: str):
    """Envuelve un flush/commit que puede chocar con una restricción única.

    Dos requests casi simultáneas (doble clic, dos pestañas abiertas) pueden
    leer el mismo "siguiente número" o el mismo folio antes de que la primera
    termine de guardar; la base de datos rechaza la segunda con
    IntegrityError. Sin esto, ese error técnico subía sin capturar hasta la
    página de error 500 genérica, en vez de un mensaje de negocio claro.
    """
    try:
        yield
    except IntegrityError:
        db.rollback()
        raise ErrorContable(mensaje) from None


@dataclass
class LineaAsiento:
    """Línea que se entrega al motor para construir un comprobante."""

    cuenta_id: int
    debe: float = 0
    haber: float = 0
    glosa: str | None = None
    centro_costo_id: int | None = None
    entidad_id: int | None = None
    documento_tipo: str | None = None
    documento_folio: str | None = None
    fecha_vencimiento: date | None = None


@dataclass
class SaldoCuenta:
    cuenta: Cuenta
    debe: float = 0
    haber: float = 0
    debe_anterior: float = 0
    haber_anterior: float = 0

    @property
    def saldo_anterior(self) -> float:
        return self.debe_anterior - self.haber_anterior

    @property
    def debe_acumulado(self) -> float:
        return self.debe + self.debe_anterior

    @property
    def haber_acumulado(self) -> float:
        return self.haber + self.haber_anterior

    @property
    def saldo(self) -> float:
        """Saldo acumulado. Positivo = deudor, negativo = acreedor."""
        return self.debe_acumulado - self.haber_acumulado

    @property
    def saldo_deudor(self) -> float:
        return self.saldo if self.saldo > 0 else 0

    @property
    def saldo_acreedor(self) -> float:
        return -self.saldo if self.saldo < 0 else 0

    # Columnas de inventario y resultado del balance de 8 columnas
    @property
    def activo(self) -> float:
        return self.saldo_deudor if self.cuenta.tipo.es_balance else 0

    @property
    def pasivo(self) -> float:
        return self.saldo_acreedor if self.cuenta.tipo.es_balance else 0

    @property
    def perdida(self) -> float:
        return self.saldo_deudor if self.cuenta.tipo.es_resultado else 0

    @property
    def ganancia(self) -> float:
        return self.saldo_acreedor if self.cuenta.tipo.es_resultado else 0


# ---------------------------------------------------------------------------
# Períodos
# ---------------------------------------------------------------------------


def periodo_cerrado(db: Session, empresa_id: int, fecha: date) -> bool:
    periodo = db.scalar(
        select(Periodo).where(
            Periodo.empresa_id == empresa_id,
            Periodo.anio == fecha.year,
            Periodo.mes == fecha.month,
        )
    )
    return bool(periodo and periodo.estado == EstadoPeriodo.CERRADO)


def exigir_periodo_abierto(db: Session, empresa_id: int, fecha: date) -> None:
    if periodo_cerrado(db, empresa_id, fecha):
        raise ErrorContable(
            f"El período {fecha.month:02d}/{fecha.year} está cerrado. "
            "Reábrelo en Contabilidad → Períodos para poder modificarlo."
        )


# ---------------------------------------------------------------------------
# Comprobantes
# ---------------------------------------------------------------------------


def siguiente_numero(db: Session, empresa_id: int, tipo: TipoComprobante, anio: int) -> int:
    maximo = db.scalar(
        select(func.max(Comprobante.numero)).where(
            Comprobante.empresa_id == empresa_id,
            Comprobante.tipo == tipo,
            Comprobante.anio == anio,
        )
    )
    return (maximo or 0) + 1


def crear_comprobante(
    db: Session,
    empresa_id: int,
    *,
    tipo: TipoComprobante,
    fecha: date,
    glosa: str,
    lineas: list[LineaAsiento],
    origen: OrigenComprobante = OrigenComprobante.MANUAL,
    origen_id: int | None = None,
    estado: EstadoComprobante = EstadoComprobante.CONTABILIZADO,
    usuario: str | None = None,
    observacion: str | None = None,
    commit: bool = True,
) -> Comprobante:
    """Crea y valida un asiento. Lanza ErrorContable si no cuadra."""
    exigir_periodo_abierto(db, empresa_id, fecha)

    lineas = [ln for ln in lineas if pesos(ln.debe) or pesos(ln.haber)]
    if len(lineas) < 2:
        raise ErrorContable("El asiento debe tener al menos dos líneas con monto.")

    total_debe = sum(pesos(ln.debe) for ln in lineas)
    total_haber = sum(pesos(ln.haber) for ln in lineas)
    if total_debe != total_haber:
        raise ErrorContable(
            f"El asiento no cuadra: debe ${total_debe:,} vs haber ${total_haber:,} "
            f"(diferencia ${abs(total_debe - total_haber):,})".replace(",", ".")
        )

    for ln in lineas:
        if pesos(ln.debe) and pesos(ln.haber):
            raise ErrorContable("Una línea no puede tener monto en el debe y en el haber.")
        cuenta = db.get(Cuenta, ln.cuenta_id)
        if cuenta is None or cuenta.empresa_id != empresa_id:
            raise ErrorContable("Cuenta contable inexistente para esta empresa.")
        if not cuenta.imputable:
            raise ErrorContable(f"La cuenta {cuenta.codigo} es de agrupación y no admite movimientos.")
        if not cuenta.activa:
            raise ErrorContable(f"La cuenta {cuenta.codigo} está inactiva.")
        if cuenta.requiere_auxiliar and not ln.entidad_id:
            raise ErrorContable(f"La cuenta {cuenta.codigo} exige indicar cliente/proveedor.")
        if cuenta.requiere_centro_costo and not ln.centro_costo_id:
            raise ErrorContable(f"La cuenta {cuenta.codigo} exige centro de costo.")

    comprobante = Comprobante(
        empresa_id=empresa_id,
        tipo=tipo,
        anio=fecha.year,
        numero=siguiente_numero(db, empresa_id, tipo, fecha.year),
        fecha=fecha,
        glosa=glosa.strip()[:300],
        estado=estado,
        origen=origen,
        origen_id=origen_id,
        total_debe=total_debe,
        total_haber=total_haber,
        observacion=observacion,
        creado_por=usuario,
    )
    for orden, ln in enumerate(lineas, start=1):
        comprobante.lineas.append(Movimiento(
            empresa_id=empresa_id,
            orden=orden,
            cuenta_id=ln.cuenta_id,
            glosa=(ln.glosa or glosa)[:300],
            debe=pesos(ln.debe),
            haber=pesos(ln.haber),
            centro_costo_id=ln.centro_costo_id,
            entidad_id=ln.entidad_id,
            documento_tipo=ln.documento_tipo,
            documento_folio=ln.documento_folio,
            fecha_vencimiento=ln.fecha_vencimiento,
        ))
    db.add(comprobante)
    mensaje_choque = (
        f"Otro proceso ya generó el comprobante N°{comprobante.numero} de tipo "
        f"{tipo.value} para {fecha.year}. Reintenta — se te asignará el siguiente número."
    )
    with capturar_integridad(db, mensaje_choque):
        if commit:
            db.commit()
        else:
            db.flush()
    return comprobante


def anular_comprobante(db: Session, comprobante: Comprobante, motivo: str = "") -> None:
    exigir_periodo_abierto(db, comprobante.empresa_id, comprobante.fecha)
    comprobante.estado = EstadoComprobante.ANULADO
    comprobante.observacion = f"{comprobante.observacion or ''}\nANULADO: {motivo}".strip()
    db.commit()


def eliminar_asiento_de(db: Session, empresa_id: int, origen: OrigenComprobante, origen_id: int) -> None:
    """Borra el asiento automático asociado a un documento (al editarlo o anularlo)."""
    comprobantes = db.scalars(
        select(Comprobante).where(
            Comprobante.empresa_id == empresa_id,
            Comprobante.origen == origen,
            Comprobante.origen_id == origen_id,
        )
    ).all()
    for comp in comprobantes:
        db.delete(comp)


# ---------------------------------------------------------------------------
# Consultas de saldos
# ---------------------------------------------------------------------------


def _base_movimientos(empresa_id: int):
    return (
        select(Movimiento)
        .join(Comprobante, Movimiento.comprobante_id == Comprobante.id)
        .where(
            Movimiento.empresa_id == empresa_id,
            Comprobante.estado == EstadoComprobante.CONTABILIZADO,
        )
    )


def sumas_por_cuenta(
    db: Session, empresa_id: int, desde: date | None, hasta: date
) -> dict[int, tuple[float, float]]:
    """Suma debe/haber por cuenta en un rango de fechas."""
    consulta = (
        select(
            Movimiento.cuenta_id,
            func.coalesce(func.sum(Movimiento.debe), 0),
            func.coalesce(func.sum(Movimiento.haber), 0),
        )
        .join(Comprobante, Movimiento.comprobante_id == Comprobante.id)
        .where(
            Movimiento.empresa_id == empresa_id,
            Comprobante.estado == EstadoComprobante.CONTABILIZADO,
            Comprobante.fecha <= hasta,
        )
        .group_by(Movimiento.cuenta_id)
    )
    if desde:
        consulta = consulta.where(Comprobante.fecha >= desde)
    return {cid: (float(d), float(h)) for cid, d, h in db.execute(consulta)}


def saldos(
    db: Session,
    empresa_id: int,
    *,
    desde: date,
    hasta: date,
    inicio_ejercicio: date | None = None,
    solo_con_movimiento: bool = True,
) -> list[SaldoCuenta]:
    """Saldos por cuenta: movimientos del período + saldo anterior acumulado.

    `inicio_ejercicio` define desde cuándo se acumula el saldo anterior; si es
    None, se acumula desde el primer movimiento registrado.
    """
    cuentas = db.scalars(
        select(Cuenta)
        .where(Cuenta.empresa_id == empresa_id, Cuenta.imputable.is_(True))
        .order_by(Cuenta.codigo)
    ).all()

    periodo = sumas_por_cuenta(db, empresa_id, desde, hasta)
    anteriores: dict[int, tuple[float, float]] = {}
    if desde:
        from datetime import timedelta

        fin_anterior = desde - timedelta(days=1)
        anteriores = sumas_por_cuenta(db, empresa_id, inicio_ejercicio, fin_anterior)

    resultado: list[SaldoCuenta] = []
    for cuenta in cuentas:
        d, h = periodo.get(cuenta.id, (0.0, 0.0))
        da, ha = anteriores.get(cuenta.id, (0.0, 0.0))
        if solo_con_movimiento and not (d or h or da or ha):
            continue
        resultado.append(SaldoCuenta(cuenta=cuenta, debe=d, haber=h, debe_anterior=da, haber_anterior=ha))
    return resultado


def libro_mayor(
    db: Session, empresa_id: int, cuenta_id: int, desde: date, hasta: date
) -> tuple[float, list[tuple[Movimiento, float]]]:
    """Devuelve (saldo anterior, [(movimiento, saldo acumulado)])."""
    from datetime import timedelta

    previos = db.execute(
        select(
            func.coalesce(func.sum(Movimiento.debe), 0),
            func.coalesce(func.sum(Movimiento.haber), 0),
        )
        .join(Comprobante, Movimiento.comprobante_id == Comprobante.id)
        .where(
            Movimiento.empresa_id == empresa_id,
            Movimiento.cuenta_id == cuenta_id,
            Comprobante.estado == EstadoComprobante.CONTABILIZADO,
            Comprobante.fecha < desde,
        )
    ).one()
    saldo = float(previos[0]) - float(previos[1])

    movimientos = db.scalars(
        _base_movimientos(empresa_id)
        .where(
            Movimiento.cuenta_id == cuenta_id,
            Comprobante.fecha >= desde,
            Comprobante.fecha <= hasta,
        )
        .options(joinedload(Movimiento.comprobante), joinedload(Movimiento.entidad))
        .order_by(Comprobante.fecha, Comprobante.numero, Movimiento.orden)
    ).unique().all()

    filas: list[tuple[Movimiento, float]] = []
    acumulado = saldo
    for mov in movimientos:
        acumulado += float(mov.debe) - float(mov.haber)
        filas.append((mov, acumulado))
    return saldo, filas


def libro_diario(
    db: Session, empresa_id: int, desde: date, hasta: date, tipo: TipoComprobante | None = None
) -> list[Comprobante]:
    consulta = (
        select(Comprobante)
        .where(
            Comprobante.empresa_id == empresa_id,
            Comprobante.fecha >= desde,
            Comprobante.fecha <= hasta,
            Comprobante.estado == EstadoComprobante.CONTABILIZADO,
        )
        .options(joinedload(Comprobante.lineas).joinedload(Movimiento.cuenta))
        .order_by(Comprobante.fecha, Comprobante.tipo, Comprobante.numero)
    )
    if tipo:
        consulta = consulta.where(Comprobante.tipo == tipo)
    return db.scalars(consulta).unique().all()


# ---------------------------------------------------------------------------
# Informes financieros
# ---------------------------------------------------------------------------


@dataclass
class GrupoInforme:
    titulo: str
    filas: list[tuple[str, str, float]] = field(default_factory=list)
    total: float = 0


def resultado_ejercicio(db: Session, empresa_id: int, desde: date, hasta: date) -> float:
    """Utilidad (+) o pérdida (-) del período."""
    filas = saldos(db, empresa_id, desde=desde, hasta=hasta, inicio_ejercicio=desde)
    ganancias = sum(f.ganancia for f in filas)
    perdidas = sum(f.perdida for f in filas)
    return ganancias - perdidas


def estado_resultados(db: Session, empresa_id: int, desde: date, hasta: date) -> dict:
    """Estado de Resultados por función, con márgenes intermedios."""
    filas = saldos(db, empresa_id, desde=desde, hasta=hasta, inicio_ejercicio=desde)

    def acumular(prefijo: str) -> tuple[list, float]:
        detalle, total = [], 0.0
        for f in filas:
            if not f.cuenta.codigo.startswith(prefijo):
                continue
            monto = f.ganancia - f.perdida if f.cuenta.tipo == TipoCuenta.GANANCIA else f.perdida - f.ganancia
            if round(monto, 2) == 0:
                continue
            detalle.append((f.cuenta.codigo, f.cuenta.nombre, monto))
            total += monto
        return detalle, total

    ingresos, total_ingresos = acumular("4.1")
    otros_ingresos, total_otros_ingresos = acumular("4.2")
    costos, total_costos = acumular("5.1")
    gastos_admin, total_gastos_admin = acumular("5.2")
    no_operacionales, total_no_op = acumular("5.3")
    impuesto, total_impuesto = acumular("5.4")

    margen_bruto = total_ingresos - total_costos
    resultado_operacional = margen_bruto - total_gastos_admin
    antes_impuesto = resultado_operacional + total_otros_ingresos - total_no_op

    return {
        "ingresos": ingresos, "total_ingresos": total_ingresos,
        "costos": costos, "total_costos": total_costos,
        "margen_bruto": margen_bruto,
        "gastos_admin": gastos_admin, "total_gastos_admin": total_gastos_admin,
        "resultado_operacional": resultado_operacional,
        "otros_ingresos": otros_ingresos, "total_otros_ingresos": total_otros_ingresos,
        "no_operacionales": no_operacionales, "total_no_operacionales": total_no_op,
        "antes_impuesto": antes_impuesto,
        "impuesto": impuesto, "total_impuesto": total_impuesto,
        "resultado_neto": antes_impuesto - total_impuesto,
    }


def balance_general(db: Session, empresa_id: int, desde: date, hasta: date) -> dict:
    """Estado de Situación Financiera clasificado."""
    filas = saldos(db, empresa_id, desde=desde, hasta=hasta, inicio_ejercicio=desde)

    def grupo(prefijo: str, titulo: str) -> GrupoInforme:
        g = GrupoInforme(titulo=titulo)
        for f in filas:
            if not f.cuenta.codigo.startswith(prefijo):
                continue
            monto = f.saldo if f.cuenta.tipo == TipoCuenta.ACTIVO else -f.saldo
            if round(monto, 2) == 0:
                continue
            g.filas.append((f.cuenta.codigo, f.cuenta.nombre, monto))
            g.total += monto
        return g

    activo_corriente = grupo("1.1", "Activo Corriente")
    activo_no_corriente = grupo("1.2", "Activo No Corriente")
    pasivo_corriente = grupo("2.1", "Pasivo Corriente")
    pasivo_no_corriente = grupo("2.2", "Pasivo No Corriente")
    patrimonio = grupo("3", "Patrimonio")

    utilidad = resultado_ejercicio(db, empresa_id, desde, hasta)
    if round(utilidad, 2) != 0:
        patrimonio.filas.append(("—", "Resultado del Ejercicio (calculado)", utilidad))
        patrimonio.total += utilidad

    total_activo = activo_corriente.total + activo_no_corriente.total
    total_pasivo = pasivo_corriente.total + pasivo_no_corriente.total
    return {
        "activo_corriente": activo_corriente,
        "activo_no_corriente": activo_no_corriente,
        "pasivo_corriente": pasivo_corriente,
        "pasivo_no_corriente": pasivo_no_corriente,
        "patrimonio": patrimonio,
        "total_activo": total_activo,
        "total_pasivo": total_pasivo,
        "total_patrimonio": patrimonio.total,
        "total_pasivo_patrimonio": total_pasivo + patrimonio.total,
        "descuadre": total_activo - (total_pasivo + patrimonio.total),
    }


def analisis_auxiliar(
    db: Session, empresa_id: int, cuenta_id: int, hasta: date
) -> list[tuple[str, str, float, float, float]]:
    """Saldos por entidad de una cuenta con auxiliar (clientes / proveedores)."""
    from contaflow.models import Entidad

    consulta = (
        select(
            Entidad.rut,
            Entidad.razon_social,
            func.coalesce(func.sum(Movimiento.debe), 0),
            func.coalesce(func.sum(Movimiento.haber), 0),
        )
        .join(Comprobante, Movimiento.comprobante_id == Comprobante.id)
        .join(Entidad, Movimiento.entidad_id == Entidad.id)
        .where(
            Movimiento.empresa_id == empresa_id,
            Movimiento.cuenta_id == cuenta_id,
            Comprobante.estado == EstadoComprobante.CONTABILIZADO,
            Comprobante.fecha <= hasta,
        )
        .group_by(Entidad.id)
        .order_by(Entidad.razon_social)
    )
    return [
        (rut, nombre, float(d), float(h), float(d) - float(h))
        for rut, nombre, d, h in db.execute(consulta)
        if round(float(d) - float(h), 2) != 0
    ]


def cerrar_ejercicio(
    db: Session, empresa_id: int, anio: int, cuenta_resultado_id: int, usuario: str | None = None
) -> Comprobante:
    """Genera el asiento de cierre que traspasa las cuentas de resultado."""
    desde, _ = rango_mes(anio, 1)
    _, hasta = rango_mes(anio, 12)
    filas = saldos(db, empresa_id, desde=desde, hasta=hasta, inicio_ejercicio=desde)

    lineas: list[LineaAsiento] = []
    neto = 0.0
    for f in filas:
        if not f.cuenta.tipo.es_resultado:
            continue
        if round(f.saldo, 2) == 0:
            continue
        if f.saldo > 0:  # saldo deudor (pérdida) → se abona para cerrar
            lineas.append(LineaAsiento(cuenta_id=f.cuenta.id, haber=f.saldo, glosa="Cierre de ejercicio"))
            neto -= f.saldo
        else:
            lineas.append(LineaAsiento(cuenta_id=f.cuenta.id, debe=-f.saldo, glosa="Cierre de ejercicio"))
            neto += -f.saldo

    if not lineas:
        raise ErrorContable("No hay cuentas de resultado con saldo para cerrar.")

    if neto >= 0:
        lineas.append(LineaAsiento(cuenta_id=cuenta_resultado_id, haber=neto, glosa="Utilidad del ejercicio"))
    else:
        lineas.append(LineaAsiento(cuenta_id=cuenta_resultado_id, debe=-neto, glosa="Pérdida del ejercicio"))

    return crear_comprobante(
        db, empresa_id,
        tipo=TipoComprobante.CIERRE,
        fecha=hasta,
        glosa=f"Cierre del ejercicio {anio}",
        lineas=lineas,
        origen=OrigenComprobante.CIERRE,
        usuario=usuario,
    )
