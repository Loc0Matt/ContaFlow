"""Cálculo de liquidaciones de sueldo según normativa laboral chilena."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.config import (
    GRATIFICACION_PORCENTAJE, GRATIFICACION_TOPE_IMM, TABLA_IMPUESTO_UNICO_UTM,
    TASAS_AFC, TASA_SALUD_LEGAL, TASA_SIS_EMPLEADOR, TOPE_IMPONIBLE_AFC_UF,
    TOPE_IMPONIBLE_AFP_UF, TOPE_IMPONIBLE_SALUD_UF,
)
from contaflow.models import (
    Comprobante, Indicador, Liquidacion, OrigenComprobante, TipoComprobante, TipoSalud, Trabajador,
)
from contaflow.services.contabilidad import (
    ErrorContable, LineaAsiento, crear_comprobante, eliminar_asiento_de,
)
from contaflow.services.seed import cuenta_parametro, valor_parametro
from contaflow.services.utils import pesos, rango_mes

#: Asignación familiar — tramos vigentes por defecto (editables en Configuración).
#: (monto por carga, tope de renta del tramo)
ASIGNACION_FAMILIAR = {
    "A": (22007, 620251),
    "B": (13505, 905941),
    "C": (4267, 1412957),
    "D": (0, None),
}


class ErrorRemuneracion(Exception):
    pass


@dataclass
class EntradaLiquidacion:
    """Datos variables del mes que se ingresan al calcular."""

    dias_trabajados: int = 30
    horas_extra: float = 0
    bonos: float = 0
    comisiones: float = 0
    otros_no_imponibles: float = 0
    anticipos: float = 0
    otros_descuentos: float = 0
    colacion: float | None = None
    movilizacion: float | None = None


def indicadores_mes(db: Session, anio: int, mes: int) -> Indicador:
    ind = db.scalar(select(Indicador).where(Indicador.anio == anio, Indicador.mes == mes))
    if ind is None or not float(ind.uf) or not float(ind.utm):
        raise ErrorRemuneracion(
            f"Faltan los indicadores de {mes:02d}/{anio} (UF, UTM e ingreso mínimo). "
            "Cárgalos en Configuración → Indicadores antes de liquidar."
        )
    return ind


def tramo_asignacion_familiar(tramo: str, renta_imponible: float) -> int:
    monto, _tope = ASIGNACION_FAMILIAR.get(tramo.upper(), (0, None))
    return monto


def impuesto_unico(base_tributable: float, utm: float) -> int:
    """Impuesto Único de Segunda Categoría sobre la base en UTM."""
    if utm <= 0:
        return 0
    base_utm = base_tributable / utm
    for desde, hasta, factor, rebaja in TABLA_IMPUESTO_UNICO_UTM:
        if base_utm > desde and (hasta is None or base_utm <= hasta):
            impuesto = base_tributable * factor - rebaja * utm
            return max(0, pesos(impuesto))
    return 0


def calcular_liquidacion(
    db: Session, trabajador: Trabajador, anio: int, mes: int, entrada: EntradaLiquidacion
) -> Liquidacion:
    """Calcula (sin guardar) la liquidación del mes para un trabajador."""
    ind = indicadores_mes(db, anio, mes)
    uf = float(ind.uf)
    utm = float(ind.utm)
    imm = float(ind.ingreso_minimo) or 0

    dias = max(1, min(30, entrada.dias_trabajados))
    proporcion = dias / 30

    sueldo_base = pesos(float(trabajador.sueldo_base) * proporcion)
    horas_extra = pesos(entrada.horas_extra)
    bonos = pesos(entrada.bonos)
    comisiones = pesos(entrada.comisiones)

    # Gratificación legal Art. 50: 25% de lo devengado, tope 4,75 IMM anual.
    base_gratificacion = sueldo_base + horas_extra + bonos + comisiones
    if trabajador.gratificacion_legal:
        tope_mensual = pesos(GRATIFICACION_TOPE_IMM * imm / 12) if imm else 0
        gratificacion = pesos(base_gratificacion * GRATIFICACION_PORCENTAJE)
        if tope_mensual:
            gratificacion = min(gratificacion, pesos(tope_mensual * proporcion))
    else:
        gratificacion = 0

    total_imponible = sueldo_base + gratificacion + horas_extra + bonos + comisiones

    # --- Topes imponibles ---------------------------------------------------
    tope_afp = pesos(TOPE_IMPONIBLE_AFP_UF * uf)
    tope_salud = pesos(TOPE_IMPONIBLE_SALUD_UF * uf)
    tope_afc = pesos(TOPE_IMPONIBLE_AFC_UF * uf)
    imponible_afp = min(total_imponible, tope_afp)
    imponible_salud = min(total_imponible, tope_salud)
    imponible_afc = min(total_imponible, tope_afc)

    # --- Cotizaciones del trabajador ----------------------------------------
    tasa_afp = 0.0 if trabajador.jubilado else float(trabajador.afp.tasa if trabajador.afp else 0)
    afp_monto = pesos(imponible_afp * tasa_afp / 100)

    salud_legal = pesos(imponible_salud * TASA_SALUD_LEGAL)
    salud_adicional = 0
    if trabajador.salud_tipo == TipoSalud.ISAPRE and float(trabajador.isapre_plan_uf or 0) > 0:
        plan_pesos = pesos(float(trabajador.isapre_plan_uf) * uf)
        salud_adicional = max(0, plan_pesos - salud_legal)

    tasa_afc_trab, tasa_afc_emp = TASAS_AFC.get(
        trabajador.tipo_contrato.value, TASAS_AFC["INDEFINIDO"]
    )
    if not trabajador.afecto_afc or trabajador.jubilado:
        tasa_afc_trab, tasa_afc_emp = 0.0, 0.0
    afc_monto = pesos(imponible_afc * tasa_afc_trab)

    # --- Impuesto único ------------------------------------------------------
    base_tributable = total_imponible - afp_monto - salud_legal - afc_monto
    impuesto = impuesto_unico(base_tributable, utm)

    # --- Haberes no imponibles ----------------------------------------------
    colacion = pesos(
        (float(trabajador.colacion) if entrada.colacion is None else entrada.colacion) * proporcion
    )
    movilizacion = pesos(
        (float(trabajador.movilizacion) if entrada.movilizacion is None else entrada.movilizacion)
        * proporcion
    )
    asignacion = pesos(
        tramo_asignacion_familiar(trabajador.asignacion_familiar_tramo, total_imponible)
        * (trabajador.cargas_familiares or 0)
    )
    otros_ni = pesos(entrada.otros_no_imponibles)
    total_no_imponible = colacion + movilizacion + asignacion + otros_ni

    total_haberes = total_imponible + total_no_imponible
    anticipos = pesos(entrada.anticipos)
    otros_desc = pesos(entrada.otros_descuentos)
    total_descuentos = (
        afp_monto + salud_legal + salud_adicional + afc_monto + impuesto + anticipos + otros_desc
    )
    liquido = total_haberes - total_descuentos

    # --- Aportes del empleador ----------------------------------------------
    sis = 0 if trabajador.jubilado else pesos(imponible_afp * TASA_SIS_EMPLEADOR)
    afc_empleador = pesos(imponible_afc * tasa_afc_emp)
    tasa_mutual = float(valor_parametro(db, trabajador.empresa_id, "tasa_mutual", "0.93") or 0.93)
    mutual = pesos(imponible_afp * tasa_mutual / 100)
    costo_empresa = total_haberes + sis + afc_empleador + mutual

    return Liquidacion(
        empresa_id=trabajador.empresa_id,
        trabajador_id=trabajador.id,
        anio=anio, mes=mes, dias_trabajados=dias,
        sueldo_base=sueldo_base, gratificacion=gratificacion, horas_extra=horas_extra,
        bonos=bonos, comisiones=comisiones, total_imponible=total_imponible,
        colacion=colacion, movilizacion=movilizacion, asignacion_familiar=asignacion,
        otros_no_imponibles=otros_ni, total_no_imponible=total_no_imponible,
        total_haberes=total_haberes,
        afp_tasa=tasa_afp, afp_monto=afp_monto, salud_monto=salud_legal,
        salud_adicional=salud_adicional, afc_monto=afc_monto,
        base_tributable=base_tributable, impuesto_unico=impuesto,
        anticipos=anticipos, otros_descuentos=otros_desc,
        total_descuentos=total_descuentos, liquido=liquido,
        sis_empleador=sis, afc_empleador=afc_empleador, mutual=mutual,
        costo_empresa=costo_empresa,
    )


def guardar_liquidacion(db: Session, liquidacion: Liquidacion) -> Liquidacion:
    existente = db.scalar(
        select(Liquidacion).where(
            Liquidacion.trabajador_id == liquidacion.trabajador_id,
            Liquidacion.anio == liquidacion.anio,
            Liquidacion.mes == liquidacion.mes,
        )
    )
    if existente:
        if existente.comprobante_id is not None:
            # Ya estaba centralizada: el asiento del mes se armó con estos
            # números — al corregirlos, ese comprobante queda desactualizado.
            # Se borra (agrupa a todos los trabajadores del mes) y hay que
            # volver a pulsar «Centralizar» para regenerarlo con lo que queda.
            eliminar_asiento_de(
                db, existente.empresa_id, OrigenComprobante.REMUNERACION,
                existente.anio * 100 + existente.mes,
            )
            existente.comprobante_id = None
        for campo in liquidacion.__table__.columns.keys():
            if campo in ("id", "creado_en", "actualizado_en", "comprobante_id"):
                continue
            setattr(existente, campo, getattr(liquidacion, campo))
        db.commit()
        return existente
    db.add(liquidacion)
    db.commit()
    return liquidacion


def eliminar_liquidacion(db: Session, liquidacion: Liquidacion) -> None:
    """Quita por completo una liquidación (a diferencia de recalcularla, que
    sólo corrige sus números).

    Si ya estaba centralizada, también borra el comprobante del mes: agrupa
    a todos los trabajadores, así que sus totales dejarían de cuadrar con
    las liquidaciones que quedan. Hay que volver a pulsar «Centralizar»
    para regenerarlo con lo que queda.
    """
    if liquidacion.comprobante_id is not None:
        eliminar_asiento_de(
            db, liquidacion.empresa_id, OrigenComprobante.REMUNERACION,
            liquidacion.anio * 100 + liquidacion.mes,
        )
    db.delete(liquidacion)
    db.commit()


def alternar_trabajador(db: Session, trabajador: Trabajador) -> bool:
    """Activa o desactiva un trabajador. Devuelve el nuevo estado.

    A diferencia de eliminarlo, esto no borra nada: sus liquidaciones y
    finiquitos anteriores quedan intactos — sólo deja de aparecer entre los
    trabajadores activos (no se le puede calcular una liquidación nueva, ni
    aparece en «Calcular todos con datos base»).
    """
    trabajador.activo = not trabajador.activo
    db.commit()
    return trabajador.activo


def eliminar_trabajador(db: Session, trabajador: Trabajador) -> None:
    """Quita por completo un trabajador — sólo si nunca se le calculó una
    liquidación.

    Si ya tiene alguna, hay que desactivarlo en vez de eliminarlo: la
    relación con Liquidacion es ondelete=CASCADE, así que borrarlo se
    llevaría esas liquidaciones consigo y dejaría sin origen cualquier
    comprobante que ya se haya centralizado con esos datos.
    """
    tiene_liquidaciones = db.scalar(
        select(Liquidacion.id).where(Liquidacion.trabajador_id == trabajador.id).limit(1)
    )
    if tiene_liquidaciones:
        raise ErrorRemuneracion(
            f"{trabajador.nombre_completo} ya tiene liquidaciones calculadas: no se puede "
            "eliminar sin perderlas. Desactívalo si ya no trabaja en la empresa."
        )
    db.delete(trabajador)
    db.commit()


def libro_remuneraciones(db: Session, empresa_id: int, anio: int, mes: int) -> list[Liquidacion]:
    from sqlalchemy.orm import joinedload

    return list(db.scalars(
        select(Liquidacion)
        .where(Liquidacion.empresa_id == empresa_id, Liquidacion.anio == anio, Liquidacion.mes == mes)
        .options(joinedload(Liquidacion.trabajador))
        .order_by(Liquidacion.id)
    ).unique().all())


def centralizar_remuneraciones(
    db: Session, empresa_id: int, anio: int, mes: int, usuario: str | None = None
) -> Comprobante:
    """Genera el asiento mensual de remuneraciones a partir de las liquidaciones."""
    liquidaciones = libro_remuneraciones(db, empresa_id, anio, mes)
    if not liquidaciones:
        raise ErrorRemuneracion(f"No hay liquidaciones calculadas para {mes:02d}/{anio}.")

    def cuenta(clave: str) -> int:
        c = cuenta_parametro(db, empresa_id, clave)
        if c is None:
            raise ErrorContable(f"Falta configurar la cuenta «{clave}».")
        return c.id

    tot = lambda campo: sum(pesos(getattr(liq, campo)) for liq in liquidaciones)  # noqa: E731

    sueldos = tot("sueldo_base") + tot("horas_extra") + tot("bonos") + tot("comisiones")
    gratificacion = tot("gratificacion")
    colacion = tot("colacion") + tot("movilizacion") + tot("otros_no_imponibles")
    asignacion = tot("asignacion_familiar")
    afp = tot("afp_monto")
    salud = tot("salud_monto") + tot("salud_adicional")
    afc_trab = tot("afc_monto")
    impuesto = tot("impuesto_unico")
    anticipos = tot("anticipos") + tot("otros_descuentos")
    liquido = tot("liquido")
    sis = tot("sis_empleador")
    afc_emp = tot("afc_empleador")
    mutual = tot("mutual")

    glosa = f"Centralización remuneraciones {mes:02d}/{anio}"
    lineas = [
        LineaAsiento(cuenta_id=cuenta("cta_sueldos_gasto"), debe=sueldos, glosa="Sueldos del mes"),
        LineaAsiento(cuenta_id=cuenta("cta_gratificacion_gasto"), debe=gratificacion,
                     glosa="Gratificación legal"),
        LineaAsiento(cuenta_id=cuenta("cta_colacion_gasto"), debe=colacion,
                     glosa="Colación y movilización"),
        LineaAsiento(cuenta_id=cuenta("cta_leyes_sociales"), debe=sis + afc_emp,
                     glosa="SIS y seguro de cesantía empleador"),
        LineaAsiento(cuenta_id=cuenta("cta_mutual_gasto"), debe=mutual, glosa="Mutual de seguridad"),
        # La asignación familiar la paga el Estado: se recupera vía caja de compensación.
        LineaAsiento(cuenta_id=cuenta("cta_afp_pagar"), haber=afp + afc_trab + afc_emp + sis,
                     glosa="Cotizaciones previsionales por pagar"),
        LineaAsiento(cuenta_id=cuenta("cta_salud_pagar"), haber=salud, glosa="Salud por pagar"),
        LineaAsiento(cuenta_id=cuenta("cta_mutual_pagar"), haber=mutual, glosa="Mutual por pagar"),
        LineaAsiento(cuenta_id=cuenta("cta_impuesto_unico"), haber=impuesto,
                     glosa="Impuesto único trabajadores"),
        LineaAsiento(cuenta_id=cuenta("cta_sueldos_pagar"), haber=liquido - asignacion,
                     glosa="Líquido por pagar"),
    ]
    if asignacion:
        lineas.append(LineaAsiento(
            cuenta_id=cuenta("cta_afp_pagar"), debe=asignacion,
            glosa="Asignación familiar (recuperable)",
        ))
        lineas.append(LineaAsiento(
            cuenta_id=cuenta("cta_sueldos_pagar"), haber=asignacion,
            glosa="Asignación familiar a pagar",
        ))
    if anticipos:
        lineas.append(LineaAsiento(
            cuenta_id=cuenta("cta_sueldos_pagar"), debe=anticipos,
            glosa="Anticipos y otros descuentos",
        ))
        lineas.append(LineaAsiento(
            cuenta_id=cuenta("cta_caja"), haber=anticipos, glosa="Anticipos ya entregados",
        ))

    _, fin = rango_mes(anio, mes)
    eliminar_asiento_de(db, empresa_id, OrigenComprobante.REMUNERACION, anio * 100 + mes)
    comprobante = crear_comprobante(
        db, empresa_id,
        tipo=TipoComprobante.TRASPASO,
        fecha=fin,
        glosa=glosa,
        lineas=lineas,
        origen=OrigenComprobante.REMUNERACION,
        origen_id=anio * 100 + mes,
        usuario=usuario,
        commit=False,
    )
    for liq in liquidaciones:
        liq.comprobante_id = comprobante.id
    db.commit()
    return comprobante


def finiquito(
    trabajador: Trabajador, fecha_termino: date, ultima_remuneracion: float,
    dias_vacaciones_pendientes: float = 0, causal_indemnizacion: bool = True,
) -> dict:
    """Cálculo referencial de finiquito (indemnizaciones y vacaciones proporcionales)."""
    inicio = trabajador.fecha_ingreso
    meses = (fecha_termino.year - inicio.year) * 12 + (fecha_termino.month - inicio.month)
    anios = meses // 12
    fraccion = meses % 12
    # Art. 163: un mes por año con tope de 11 años; fracción > 6 meses se considera año completo.
    anios_indemnizables = min(11, anios + (1 if fraccion > 6 else 0))

    base = pesos(ultima_remuneracion)
    indem_anios = pesos(base * anios_indemnizables) if causal_indemnizacion and anios >= 1 else 0
    indem_aviso = pesos(base) if causal_indemnizacion else 0
    vacaciones = pesos(base / 30 * dias_vacaciones_pendientes)

    return {
        "meses_servicio": meses,
        "anios_indemnizables": anios_indemnizables,
        "indemnizacion_anios_servicio": indem_anios,
        "indemnizacion_aviso_previo": indem_aviso,
        "feriado_proporcional": vacaciones,
        "total": indem_anios + indem_aviso + vacaciones,
    }
