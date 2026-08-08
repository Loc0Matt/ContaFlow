"""Propuestas de Formulario 29 (IVA mensual) y Formulario 22 (Renta anual).

IMPORTANTE: el sistema no se conecta al SII. Lo que se genera aquí es una
*propuesta* con los códigos calculados desde la contabilidad, pensada para
traspasar los valores al formulario oficial. Verifica siempre los códigos
contra el formulario vigente del año antes de declarar.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contaflow.config import RETENCION_HONORARIOS, RETENCION_HONORARIOS_DEFECTO
from contaflow.models import Declaracion, Empresa, Liquidacion, RegimenTributario
from contaflow.services.contabilidad import estado_resultados
from contaflow.services.libros import agrupar_para_f29
from contaflow.services.utils import mes_anterior, pesos, rango_mes


@dataclass
class CodigoFormulario:
    codigo: str
    etiqueta: str
    valor: int
    seccion: str
    nota: str = ""


@dataclass
class PropuestaF29:
    empresa: str
    rut: str
    anio: int
    mes: int
    codigos: list[CodigoFormulario] = field(default_factory=list)
    iva_determinado: int = 0
    remanente_anterior: int = 0
    remanente_siguiente: int = 0
    total_a_pagar: int = 0
    advertencias: list[str] = field(default_factory=list)

    def por_seccion(self) -> dict[str, list[CodigoFormulario]]:
        agrupado: dict[str, list[CodigoFormulario]] = {}
        for c in self.codigos:
            agrupado.setdefault(c.seccion, []).append(c)
        return agrupado

    def como_dict(self) -> dict:
        return {c.codigo: c.valor for c in self.codigos}


def tasa_retencion_honorarios(anio: int) -> float:
    return RETENCION_HONORARIOS.get(anio, RETENCION_HONORARIOS_DEFECTO)


def remanente_previo(db: Session, empresa_id: int, anio: int, mes: int) -> int:
    """Remanente de crédito fiscal declarado en el F29 del mes anterior."""
    a_ant, m_ant = mes_anterior(anio, mes)
    previa = db.scalar(
        select(Declaracion).where(
            Declaracion.empresa_id == empresa_id,
            Declaracion.formulario == "F29",
            Declaracion.anio == a_ant,
            Declaracion.mes == m_ant,
        )
    )
    return pesos(previa.remanente_siguiente) if previa else 0


def generar_f29(
    db: Session,
    empresa: Empresa,
    anio: int,
    mes: int,
    *,
    remanente_anterior: int | None = None,
    ppm_tasa: float | None = None,
    creditos_sence: int = 0,
    otros_creditos: int = 0,
) -> PropuestaF29:
    """Calcula la propuesta de F29 del período a partir de los libros de IVA."""
    g = agrupar_para_f29(db, empresa.id, anio, mes)
    if remanente_anterior is None:
        remanente_anterior = remanente_previo(db, empresa.id, anio, mes)
    tasa_ppm = float(empresa.tasa_ppm if ppm_tasa is None else ppm_tasa)

    prop = PropuestaF29(
        empresa=empresa.razon_social, rut=empresa.rut, anio=anio, mes=mes,
        remanente_anterior=remanente_anterior,
    )
    add = lambda c, e, v, s, n="": prop.codigos.append(  # noqa: E731
        CodigoFormulario(codigo=c, etiqueta=e, valor=pesos(v), seccion=s, nota=n)
    )

    # ---------------------------------------------------------------- DÉBITOS
    S = "DÉBITOS Y VENTAS"
    add("110", "Boletas — cantidad de documentos", g.boletas_cant, S)
    add("111", "Boletas — débitos", g.boletas_iva, S)
    add("503", "Facturas emitidas — cantidad de documentos", g.facturas_afectas_cant, S)
    add("502", "Facturas emitidas — débitos", g.facturas_afectas_iva, S)
    add("509", "Notas de crédito emitidas — cantidad", g.nc_emitidas_cant, S)
    add("510", "Notas de crédito emitidas — débitos (rebaja)", g.nc_emitidas_iva, S)
    add("512", "Notas de débito emitidas — cantidad", g.nd_emitidas_cant, S)
    add("513", "Notas de débito emitidas — débitos", g.nd_emitidas_iva, S)
    add("142", "Ventas y servicios exentos o no gravados",
        g.facturas_exentas_monto + g.boletas_exentas_monto, S)
    add("585", "Exportaciones — monto neto", g.exportaciones_monto, S)

    monto_neto_ventas = (
        g.facturas_afectas_neto + g.boletas_neto + g.nd_emitidas_neto - g.nc_emitidas_neto
    )
    add("563", "Monto neto de ventas y servicios del giro", monto_neto_ventas, S,
        "Base de los PPM de Primera Categoría")

    total_debitos = g.facturas_afectas_iva + g.boletas_iva + g.nd_emitidas_iva - g.nc_emitidas_iva
    add("537", "TOTAL DÉBITOS", total_debitos, S)

    # ---------------------------------------------------------------- CRÉDITOS
    S = "CRÉDITOS Y COMPRAS"
    add("519", "Facturas recibidas del giro — cantidad", g.compras_giro_cant, S)
    add("520", "Facturas recibidas del giro — crédito recuperable", g.compras_giro_iva, S)
    add("524", "Facturas activo fijo — cantidad", g.compras_af_cant, S)
    add("525", "Facturas activo fijo — crédito recuperable", g.compras_af_iva, S)
    add("527", "Notas de crédito recibidas — cantidad", g.nc_recibidas_cant, S)
    add("528", "Notas de crédito recibidas — crédito (rebaja)", g.nc_recibidas_iva, S)
    add("531", "Notas de débito recibidas — cantidad", g.nd_recibidas_cant, S)
    add("532", "Notas de débito recibidas — crédito", g.nd_recibidas_iva, S)
    add("534", "Importaciones (DIN) — cantidad", g.importaciones_cant, S)
    add("535", "Importaciones — crédito recuperable", g.importaciones_iva, S)
    add("553", "Compras supermercado — cantidad", g.compras_supermercado_cant, S)
    add("554", "Compras supermercado — crédito", g.compras_supermercado_iva, S)
    add("564", "Monto neto de compras y servicios recibidos",
        g.compras_giro_neto + g.compras_af_neto, S)
    add("520.1", "IVA de uso común del período", g.compras_uso_comun_iva, S,
        "Aplicar el factor de proporcionalidad antes de declarar")
    add("564.1", "IVA sin derecho a crédito (no recuperable)", g.compras_sin_derecho_monto, S,
        "Va a resultado, no al crédito fiscal")

    total_creditos = (
        g.compras_giro_iva + g.compras_af_iva + g.nd_recibidas_iva - g.nc_recibidas_iva
        + g.importaciones_iva + g.compras_supermercado_iva + g.compras_uso_comun_iva
    )
    add("504", "Remanente de crédito fiscal del mes anterior", remanente_anterior, S)
    add("538", "TOTAL CRÉDITOS", total_creditos, S)

    # ------------------------------------------------------------ DETERMINACIÓN
    S = "DETERMINACIÓN DEL IVA"
    determinado = total_debitos - total_creditos - remanente_anterior
    prop.iva_determinado = determinado
    if determinado >= 0:
        add("89", "IVA determinado a pagar", determinado, S)
        add("77", "Remanente de crédito fiscal período siguiente", 0, S)
        prop.remanente_siguiente = 0
        iva_a_pagar = determinado
    else:
        add("89", "IVA determinado a pagar", 0, S)
        add("77", "Remanente de crédito fiscal período siguiente", -determinado, S)
        prop.remanente_siguiente = -determinado
        iva_a_pagar = 0

    # -------------------------------------------------------------- RETENCIONES
    S = "RETENCIONES E IMPUESTOS ADICIONALES"
    add("151", "Retención honorarios Art. 42 N°2", g.honorarios_retencion, S,
        f"Tasa {tasa_retencion_honorarios(anio) * 100:.2f}% · {g.honorarios_cant} boleta(s)")
    add("152", "Honorarios brutos pagados en el período", g.honorarios_bruto, S)

    impuesto_unico = pesos(db.scalar(
        select(func.coalesce(func.sum(Liquidacion.impuesto_unico), 0)).where(
            Liquidacion.empresa_id == empresa.id,
            Liquidacion.anio == anio,
            Liquidacion.mes == mes,
        )
    ) or 0)
    add("48", "Retención Impuesto Único a los Trabajadores", impuesto_unico, S)
    add("39", "Retención cambio de sujeto (facturas de compra)",
        g.compras_retencion + g.ventas_retencion, S)

    # --------------------------------------------------------------------- PPM
    S = "PPM E IMPUESTO A LA RENTA"
    ppm_bruto = pesos(monto_neto_ventas * tasa_ppm / 100)
    add("115", f"Tasa PPM aplicada ({tasa_ppm:.3f}%)", ppm_bruto, S,
        f"{monto_neto_ventas:,} × {tasa_ppm:.3f}%".replace(",", "."))
    add("62", "PPM neto determinado", max(0, ppm_bruto - creditos_sence), S)
    if creditos_sence:
        add("66", "Crédito por gastos de capacitación (SENCE)", creditos_sence, S)

    if empresa.regimen == RegimenTributario.ART14D8:
        prop.advertencias.append(
            "Régimen 14 D N°8 (Pro Pyme Transparente): los PPM tienen tasa especial "
            "(0,2% el primer año, 0,5% después). Verifica la tasa antes de declarar."
        )

    # ------------------------------------------------------------------ TOTALES
    S = "TOTALES"
    ppm_neto = max(0, ppm_bruto - creditos_sence)
    total = (
        iva_a_pagar + ppm_neto + g.honorarios_retencion + impuesto_unico
        + g.compras_retencion + g.ventas_retencion - otros_creditos
    )
    add("547", "TOTAL DETERMINADO", total, S)
    add("91", "TOTAL A PAGAR DENTRO DEL PLAZO LEGAL", max(0, total), S)
    prop.total_a_pagar = max(0, total)

    if remanente_anterior and total_debitos == 0 and total_creditos == 0:
        prop.advertencias.append("El período no registra documentos: revisa antes de declarar.")
    prop.advertencias.append(
        "Los códigos son una propuesta calculada desde tu contabilidad. "
        "Contrástalos con el formulario oficial vigente antes de presentar la declaración."
    )
    return prop


def guardar_f29(db: Session, empresa_id: int, prop: PropuestaF29) -> Declaracion:
    decl = db.scalar(
        select(Declaracion).where(
            Declaracion.empresa_id == empresa_id,
            Declaracion.formulario == "F29",
            Declaracion.anio == prop.anio,
            Declaracion.mes == prop.mes,
        )
    )
    if decl is None:
        decl = Declaracion(
            empresa_id=empresa_id, formulario="F29", anio=prop.anio, mes=prop.mes
        )
        db.add(decl)
    decl.codigos_json = json.dumps(
        [asdict(c) for c in prop.codigos], ensure_ascii=False
    )
    decl.total_a_pagar = prop.total_a_pagar
    decl.remanente_siguiente = prop.remanente_siguiente
    db.commit()
    return decl


# ---------------------------------------------------------------------------
# Formulario 22 — Renta anual
# ---------------------------------------------------------------------------


@dataclass
class PropuestaF22:
    empresa: str
    rut: str
    anio_comercial: int
    codigos: list[CodigoFormulario] = field(default_factory=list)
    rli: int = 0
    impuesto_primera: int = 0
    ppm_actualizados: int = 0
    saldo: int = 0
    advertencias: list[str] = field(default_factory=list)

    def por_seccion(self) -> dict[str, list[CodigoFormulario]]:
        agrupado: dict[str, list[CodigoFormulario]] = {}
        for c in self.codigos:
            agrupado.setdefault(c.seccion, []).append(c)
        return agrupado


TASAS_PRIMERA_CATEGORIA = {
    RegimenTributario.ART14A: 0.27,
    RegimenTributario.ART14D3: 0.25,
    RegimenTributario.ART14D8: 0.0,   # tributan los dueños, la empresa queda liberada
    RegimenTributario.RENTA_PRESUNTA: 0.25,
    RegimenTributario.CONTRIBUYENTE_2A: 0.0,
}


def generar_f22(
    db: Session,
    empresa: Empresa,
    anio: int,
    *,
    agregados: int = 0,
    deducciones: int = 0,
    perdida_ejercicios_anteriores: int = 0,
    ppm_pagados: int = 0,
    creditos_impuesto: int = 0,
) -> PropuestaF22:
    """Determina la Renta Líquida Imponible partiendo del resultado financiero.

    Los agregados (gastos rechazados) y deducciones (ingresos no renta) se
    ingresan manualmente: dependen del análisis del contador.
    """
    desde, _ = rango_mes(anio, 1)
    _, hasta = rango_mes(anio, 12)
    eerr = estado_resultados(db, empresa.id, desde, hasta)
    resultado_financiero = pesos(eerr["antes_impuesto"])

    prop = PropuestaF22(
        empresa=empresa.razon_social, rut=empresa.rut, anio_comercial=anio,
    )
    add = lambda c, e, v, s, n="": prop.codigos.append(  # noqa: E731
        CodigoFormulario(codigo=c, etiqueta=e, valor=pesos(v), seccion=s, nota=n)
    )

    S = "DETERMINACIÓN RENTA LÍQUIDA IMPONIBLE"
    add("636", "Resultado financiero según balance (antes de impuesto)", resultado_financiero, S)
    add("637", "Agregados: gastos rechazados y no aceptados", agregados, S,
        "Multas fiscales, gastos sin respaldo, retiros, Art. 21 LIR")
    add("638", "Deducciones: ingresos no renta y rentas exentas", deducciones, S)

    rli_bruta = resultado_financiero + agregados - deducciones
    add("643", "Renta líquida antes de pérdidas de arrastre", rli_bruta, S)
    add("634", "Pérdida tributaria de ejercicios anteriores", perdida_ejercicios_anteriores, S)

    rli = rli_bruta - perdida_ejercicios_anteriores
    prop.rli = rli
    add("643.1", "RENTA LÍQUIDA IMPONIBLE", max(0, rli), S)
    if rli < 0:
        add("634.1", "Pérdida tributaria a ejercicio siguiente", -rli, S)

    S = "IMPUESTO DE PRIMERA CATEGORÍA"
    tasa = TASAS_PRIMERA_CATEGORIA.get(empresa.regimen, 0.25)
    impuesto = pesos(max(0, rli) * tasa)
    prop.impuesto_primera = impuesto
    add("18", f"Impuesto Primera Categoría ({tasa * 100:.0f}%)", impuesto, S,
        empresa.regimen.etiqueta)
    add("365", "Créditos contra el impuesto de Primera Categoría", creditos_impuesto, S)

    S = "PAGOS PROVISIONALES Y SALDO"
    add("36", "PPM pagados durante el ejercicio (actualizados)", ppm_pagados, S)
    prop.ppm_actualizados = ppm_pagados
    saldo = impuesto - creditos_impuesto - ppm_pagados
    prop.saldo = saldo
    if saldo >= 0:
        add("91", "Impuesto a pagar", saldo, S)
        add("87", "Remanente / devolución solicitada", 0, S)
    else:
        add("91", "Impuesto a pagar", 0, S)
        add("87", "Remanente / devolución solicitada", -saldo, S)

    if empresa.regimen == RegimenTributario.ART14D8:
        prop.advertencias.append(
            "Régimen 14 D N°8 (Transparente): la empresa está liberada del Impuesto de "
            "Primera Categoría; la base se asigna a los dueños en su Global Complementario."
        )
    prop.advertencias.append(
        "Propuesta calculada desde el balance. No incluye corrección monetaria ni la "
        "determinación de los registros empresariales (RAI, DDAN, REX, SAC), "
        "que deben analizarse aparte."
    )
    return prop


def guardar_f22(db: Session, empresa_id: int, prop: PropuestaF22) -> Declaracion:
    decl = db.scalar(
        select(Declaracion).where(
            Declaracion.empresa_id == empresa_id,
            Declaracion.formulario == "F22",
            Declaracion.anio == prop.anio_comercial,
            Declaracion.mes == 0,
        )
    )
    if decl is None:
        decl = Declaracion(empresa_id=empresa_id, formulario="F22", anio=prop.anio_comercial, mes=0)
        db.add(decl)
    decl.codigos_json = json.dumps([asdict(c) for c in prop.codigos], ensure_ascii=False)
    decl.total_a_pagar = max(0, prop.saldo)
    db.commit()
    return decl
