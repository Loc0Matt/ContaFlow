"""Activo fijo: tabla de vidas útiles del SII, depreciación y bajas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from contaflow.models import (
    ActivoFijo, Comprobante, Cuenta, Depreciacion, OrigenComprobante, TipoComprobante,
)
from contaflow.services.contabilidad import (
    ErrorContable, LineaAsiento, crear_comprobante, eliminar_asiento_de,
)
from contaflow.services.seed import cuenta_parametro
from contaflow.services.utils import pesos, rango_mes

#: Vidas útiles normales según Resolución Ex. N°43 de 2002 del SII (en años).
VIDAS_UTILES_SII: list[tuple[str, int]] = [
    ("Construcciones de material sólido", 80),
    ("Construcciones de adobe o madera", 30),
    ("Galpones de estructura metálica", 20),
    ("Instalaciones (sanitarias, eléctricas, redes)", 10),
    ("Maquinarias y equipos en general", 15),
    ("Vehículos motorizados en general (automóviles, camionetas)", 7),
    ("Camiones de uso general", 7),
    ("Muebles y enseres", 7),
    ("Herramientas pesadas", 8),
    ("Herramientas livianas", 3),
    ("Equipos de computación (hardware)", 6),
    ("Sistemas y programas computacionales (software)", 6),
    ("Máquinas de oficina (fotocopiadoras, impresoras)", 6),
    ("Estanques y contenedores", 10),
    ("Equipos de aire acondicionado", 10),
]


@dataclass
class FilaDepreciacion:
    anio: int
    mes: int
    monto: int
    acumulado: int
    valor_libro: int


def calendario_depreciacion(activo: ActivoFijo, hasta: date | None = None) -> list[FilaDepreciacion]:
    """Genera la tabla de depreciación lineal mensual del activo.

    La depreciación comienza el mes siguiente al de la adquisición, criterio
    habitual para el registro tributario chileno.
    """
    filas: list[FilaDepreciacion] = []
    meses = activo.vida_util_efectiva
    depreciable = pesos(activo.depreciable)
    if meses <= 0 or depreciable <= 0:
        return filas

    cuota = depreciable // meses
    resto = depreciable - cuota * meses

    anio = activo.fecha_adquisicion.year
    mes = activo.fecha_adquisicion.month
    acumulado = 0
    for i in range(meses):
        mes += 1
        if mes > 12:
            mes, anio = 1, anio + 1
        monto = cuota + (resto if i == meses - 1 else 0)
        acumulado += monto
        fila = FilaDepreciacion(
            anio=anio, mes=mes, monto=monto, acumulado=acumulado,
            valor_libro=pesos(activo.valor_adquisicion) - acumulado,
        )
        if hasta and date(anio, mes, 1) > hasta:
            break
        filas.append(fila)
    return filas


def depreciacion_del_mes(activo: ActivoFijo, anio: int, mes: int) -> int:
    for fila in calendario_depreciacion(activo):
        if fila.anio == anio and fila.mes == mes:
            return fila.monto
    return 0


def acumulada_hasta(activo: ActivoFijo, anio: int, mes: int) -> int:
    total = 0
    for fila in calendario_depreciacion(activo):
        if (fila.anio, fila.mes) <= (anio, mes):
            total = fila.acumulado
    return total


def activos_vigentes(db: Session, empresa_id: int) -> list[ActivoFijo]:
    return list(db.scalars(
        select(ActivoFijo)
        .where(ActivoFijo.empresa_id == empresa_id, ActivoFijo.dado_de_baja.is_(False))
        .order_by(ActivoFijo.codigo)
    ).all())


def procesar_depreciacion_mensual(
    db: Session, empresa_id: int, anio: int, mes: int, usuario: str | None = None
) -> tuple[Comprobante | None, list[Depreciacion]]:
    """Calcula y contabiliza la depreciación de todos los activos del período."""
    activos = activos_vigentes(db, empresa_id)
    registros: list[Depreciacion] = []
    total = 0

    for activo in activos:
        monto = depreciacion_del_mes(activo, anio, mes)
        if monto <= 0:
            continue
        existente = db.scalar(
            select(Depreciacion).where(
                Depreciacion.activo_id == activo.id,
                Depreciacion.anio == anio,
                Depreciacion.mes == mes,
            )
        )
        acumulado = acumulada_hasta(activo, anio, mes)
        valor_libro = pesos(activo.valor_adquisicion) - acumulado
        if existente:
            existente.monto = monto
            existente.acumulado = acumulado
            existente.valor_libro = valor_libro
            registros.append(existente)
        else:
            registro = Depreciacion(
                activo_id=activo.id, empresa_id=empresa_id, anio=anio, mes=mes,
                monto=monto, acumulado=acumulado, valor_libro=valor_libro,
            )
            db.add(registro)
            registros.append(registro)
        total += monto

    if total == 0:
        db.commit()
        return None, registros

    cuenta_gasto = cuenta_parametro(db, empresa_id, "cta_depreciacion_gasto")
    cuenta_acum = cuenta_parametro(db, empresa_id, "cta_depreciacion_acum")
    if not cuenta_gasto or not cuenta_acum:
        raise ErrorContable(
            "Configura las cuentas de depreciación en Configuración → Cuentas contables."
        )

    # Cada activo puede tener su propia cuenta de depreciación acumulada.
    por_cuenta: dict[int, int] = {}
    for registro in registros:
        activo = db.get(ActivoFijo, registro.activo_id)
        cuenta_id = activo.cuenta_depreciacion_id or cuenta_acum.id
        por_cuenta[cuenta_id] = por_cuenta.get(cuenta_id, 0) + pesos(registro.monto)

    lineas = [LineaAsiento(cuenta_id=cuenta_gasto.id, debe=total, glosa="Depreciación del período")]
    for cuenta_id, monto in por_cuenta.items():
        lineas.append(LineaAsiento(cuenta_id=cuenta_id, haber=monto, glosa="Depreciación acumulada"))

    _, fin = rango_mes(anio, mes)
    eliminar_asiento_de(db, empresa_id, OrigenComprobante.DEPRECIACION, anio * 100 + mes)
    comprobante = crear_comprobante(
        db, empresa_id,
        tipo=TipoComprobante.TRASPASO,
        fecha=fin,
        glosa=f"Depreciación del ejercicio {mes:02d}/{anio}",
        lineas=lineas,
        origen=OrigenComprobante.DEPRECIACION,
        origen_id=anio * 100 + mes,
        usuario=usuario,
        commit=False,
    )
    for registro in registros:
        registro.comprobante_id = comprobante.id
    db.commit()
    return comprobante, registros


def dar_de_baja(
    db: Session, activo: ActivoFijo, fecha: date, valor_venta: float = 0,
    cuenta_contrapartida_id: int | None = None, usuario: str | None = None,
) -> Comprobante:
    """Registra la baja o venta del activo con su resultado."""
    acumulado = acumulada_hasta(activo, fecha.year, fecha.month)
    costo = pesos(activo.valor_adquisicion)
    valor_libro = costo - acumulado
    venta = pesos(valor_venta)
    resultado = venta - valor_libro

    def _por_codigo(codigo: str) -> Cuenta:
        cuenta = db.scalar(
            select(Cuenta).where(Cuenta.empresa_id == activo.empresa_id, Cuenta.codigo == codigo)
        )
        if cuenta is None:
            raise ErrorContable(f"Falta la cuenta {codigo} en el plan de cuentas.")
        return cuenta

    def _defecto(clave: str) -> int:
        cuenta = cuenta_parametro(db, activo.empresa_id, clave)
        if cuenta is None:
            raise ErrorContable(f"Falta configurar la cuenta «{clave}».")
        return cuenta.id

    cuenta_activo = activo.cuenta_activo_id or _defecto("cta_activo_fijo")
    cuenta_acum = activo.cuenta_depreciacion_id or _defecto("cta_depreciacion_acum")
    contrapartida = cuenta_contrapartida_id or _defecto("cta_caja")

    lineas = [
        LineaAsiento(cuenta_id=cuenta_acum, debe=acumulado, glosa="Baja depreciación acumulada"),
        LineaAsiento(cuenta_id=cuenta_activo, haber=costo, glosa=f"Baja activo {activo.codigo}"),
    ]
    if venta:
        lineas.append(LineaAsiento(cuenta_id=contrapartida, debe=venta, glosa="Venta de activo fijo"))

    if resultado > 0:
        lineas.append(LineaAsiento(
            cuenta_id=_por_codigo("4.2.01.002").id, haber=resultado,
            glosa="Utilidad en venta de activo fijo",
        ))
    elif resultado < 0:
        lineas.append(LineaAsiento(
            cuenta_id=_por_codigo("5.3.01.002").id, debe=-resultado,
            glosa="Pérdida en baja de activo fijo",
        ))

    comprobante = crear_comprobante(
        db, activo.empresa_id,
        tipo=TipoComprobante.TRASPASO,
        fecha=fecha,
        glosa=f"Baja de activo fijo {activo.codigo} · {activo.nombre}",
        lineas=lineas,
        usuario=usuario,
        commit=False,
    )
    activo.dado_de_baja = True
    activo.fecha_baja = fecha
    activo.valor_venta = venta
    db.commit()
    return comprobante


def resumen_activo_fijo(db: Session, empresa_id: int, anio: int, mes: int) -> list[dict]:
    """Tabla del libro de activo fijo al cierre del período."""
    activos = db.scalars(
        select(ActivoFijo)
        .where(ActivoFijo.empresa_id == empresa_id)
        .options(joinedload(ActivoFijo.depreciaciones))
        .order_by(ActivoFijo.codigo)
    ).unique().all()

    filas = []
    for activo in activos:
        acumulado = acumulada_hasta(activo, anio, mes)
        costo = pesos(activo.valor_adquisicion)
        filas.append({
            "activo": activo,
            "costo": costo,
            "depreciacion_mes": depreciacion_del_mes(activo, anio, mes),
            "depreciacion_acumulada": acumulado,
            "valor_libro": costo - acumulado,
            "vida_util": activo.vida_util_efectiva,
        })
    return filas
