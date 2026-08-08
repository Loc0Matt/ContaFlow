"""Documentos tributarios: cálculo de IVA y centralización contable automática."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.config import TASA_IVA
from contaflow.models import (
    ClaseDocumento, Comprobante, Documento, Entidad, Honorario, OrigenComprobante, TipoCompra,
    TipoComprobante, TipoDTE,
)
from contaflow.services.contabilidad import (
    ErrorContable, LineaAsiento, crear_comprobante, eliminar_asiento_de,
)
from contaflow.services.seed import cuenta_parametro, valor_parametro
from contaflow.services.utils import normalizar_rut, pesos, redondear

#: Tipos de documento agrupados como los pide el F29.
FACTURAS_AFECTAS = {30, 33, 45, 46, 43}
FACTURAS_EXENTAS = {32, 34}
BOLETAS = {35, 39, 48}
BOLETAS_EXENTAS = {38, 41}
NOTAS_CREDITO = {60, 61, 112}
NOTAS_DEBITO = {55, 56, 111}
EXPORTACIONES = {101, 110, 111, 112}
IMPORTACIONES = {914}
GUIAS = {50, 52}
FACTURAS_COMPRA = {45, 46}


def calcular_iva(neto: float, tasa: float = TASA_IVA) -> int:
    """IVA con redondeo comercial, tal como lo calcula el SII."""
    return pesos(redondear(float(neto) * tasa, 0))


def neto_desde_total(total: float, tasa: float = TASA_IVA) -> int:
    """Despeja el neto a partir de un total con IVA incluido (boletas)."""
    return pesos(redondear(float(total) / (1 + tasa), 0))


def totalizar(
    *,
    neto: float = 0,
    exento: float = 0,
    iva: float | None = None,
    impuesto_adicional: float = 0,
    retencion: float = 0,
    iva_no_recuperable: float = 0,
) -> dict[str, int]:
    """Calcula el total del documento. Si `iva` es None se deriva del neto."""
    neto_i = pesos(neto)
    exento_i = pesos(exento)
    iva_i = calcular_iva(neto_i) if iva is None else pesos(iva)
    adicional_i = pesos(impuesto_adicional)
    retencion_i = pesos(retencion)
    no_rec_i = pesos(iva_no_recuperable)
    total = neto_i + exento_i + iva_i + no_rec_i + adicional_i - retencion_i
    return {
        "neto": neto_i, "exento": exento_i, "iva": iva_i,
        "impuesto_adicional": adicional_i, "retencion": retencion_i,
        "iva_no_recuperable": no_rec_i, "total": total,
    }


def _cuenta_id(db: Session, empresa_id: int, clave: str) -> int:
    cuenta = cuenta_parametro(db, empresa_id, clave)
    if cuenta is None:
        raise ErrorContable(
            f"Falta configurar la cuenta «{clave}» en Configuración → Cuentas contables."
        )
    return cuenta.id


def obtener_o_crear_entidad(
    db: Session, empresa_id: int, rut: str, nombre: str, *, cliente=False, proveedor=False
) -> Entidad:
    rut_norm = normalizar_rut(rut)
    entidad = db.scalar(
        select(Entidad).where(Entidad.empresa_id == empresa_id, Entidad.rut == rut_norm)
    )
    if entidad is None:
        entidad = Entidad(
            empresa_id=empresa_id, rut=rut_norm, razon_social=nombre.strip()[:200],
            es_cliente=cliente, es_proveedor=proveedor,
        )
        db.add(entidad)
        db.flush()
    else:
        entidad.es_cliente = entidad.es_cliente or cliente
        entidad.es_proveedor = entidad.es_proveedor or proveedor
    return entidad


# ---------------------------------------------------------------------------
# Centralización contable
# ---------------------------------------------------------------------------


def generar_asiento_documento(
    db: Session,
    documento: Documento,
    *,
    cuenta_contrapartida_id: int | None = None,
    cuenta_resultado_id: int | None = None,
    centro_costo_id: int | None = None,
    usuario: str | None = None,
) -> Comprobante:
    """Crea el asiento de una venta o compra.

    - `cuenta_contrapartida_id`: clientes/proveedores por defecto, o caja/banco
      si el documento se registra como pagado al contado.
    - `cuenta_resultado_id`: cuenta de ingreso (ventas) o de gasto/costo (compras).
    """
    empresa_id = documento.empresa_id
    tipo_dte = db.get(TipoDTE, documento.tipo_dte)
    signo = tipo_dte.signo if tipo_dte else 1
    es_venta = documento.clase == ClaseDocumento.VENTA

    neto = pesos(documento.neto)
    exento = pesos(documento.exento)
    iva = pesos(documento.iva)
    no_rec = pesos(documento.iva_no_recuperable)
    adicional = pesos(documento.impuesto_adicional)
    retencion = pesos(documento.retencion)
    total = pesos(documento.total)

    lineas: list[LineaAsiento] = []
    glosa = f"{tipo_dte.nombre if tipo_dte else 'DTE'} N°{documento.folio} · {documento.entidad_nombre}"
    ref = dict(
        documento_tipo=str(documento.tipo_dte),
        documento_folio=documento.folio,
        entidad_id=documento.entidad_id,
        glosa=glosa,
    )

    def agregar(cuenta_id: int, monto: int, al_debe: bool, **extra):
        """Aplica el signo del documento: una NC invierte debe/haber."""
        if not monto:
            return
        neto_debe = al_debe if signo > 0 else not al_debe
        datos = {**ref, **extra}
        lineas.append(LineaAsiento(
            cuenta_id=cuenta_id,
            debe=monto if neto_debe else 0,
            haber=0 if neto_debe else monto,
            **datos,
        ))

    if es_venta:
        contrapartida = cuenta_contrapartida_id or _cuenta_id(db, empresa_id, "cta_clientes")
        agregar(contrapartida, total, al_debe=True, fecha_vencimiento=documento.fecha_vencimiento)
        if neto:
            cuenta_ingreso = cuenta_resultado_id or _cuenta_id(db, empresa_id, "cta_ventas_afectas")
            agregar(cuenta_ingreso, neto, al_debe=False, centro_costo_id=centro_costo_id)
        if exento:
            cuenta_ex = _cuenta_id(
                db, empresa_id,
                "cta_ventas_exportacion" if documento.tipo_dte in EXPORTACIONES else "cta_ventas_exentas",
            )
            agregar(cuenta_ex, exento, al_debe=False, centro_costo_id=centro_costo_id)
        if iva:
            agregar(_cuenta_id(db, empresa_id, "cta_iva_debito"), iva, al_debe=False)
        if adicional:
            agregar(_cuenta_id(db, empresa_id, "cta_impuesto_adicional"), adicional, al_debe=False)
        if retencion:
            # Factura de compra emitida por el cliente: nos retiene el IVA.
            agregar(_cuenta_id(db, empresa_id, "cta_retencion_sujeto"), retencion, al_debe=True)
        tipo_comprobante = TipoComprobante.INGRESO
        origen = OrigenComprobante.VENTA
    else:
        contrapartida = cuenta_contrapartida_id or _cuenta_id(db, empresa_id, "cta_proveedores")
        if documento.tipo_compra == TipoCompra.ACTIVO_FIJO:
            clave_gasto = "cta_activo_fijo"
        else:
            clave_gasto = "cta_compras"
        cuenta_gasto = cuenta_resultado_id or _cuenta_id(db, empresa_id, clave_gasto)
        if neto:
            agregar(cuenta_gasto, neto, al_debe=True, centro_costo_id=centro_costo_id)
        if exento:
            agregar(cuenta_gasto, exento, al_debe=True, centro_costo_id=centro_costo_id)
        if iva:
            clave_iva = (
                "cta_iva_credito_af" if documento.tipo_compra == TipoCompra.ACTIVO_FIJO
                else "cta_iva_credito"
            )
            agregar(_cuenta_id(db, empresa_id, clave_iva), iva, al_debe=True)
        if no_rec:
            agregar(_cuenta_id(db, empresa_id, "cta_iva_no_recuperable"), no_rec, al_debe=True,
                    centro_costo_id=centro_costo_id)
        if adicional:
            agregar(cuenta_gasto, adicional, al_debe=True, centro_costo_id=centro_costo_id)
        if retencion:
            # Factura de compra emitida por nosotros: retenemos el IVA al proveedor.
            agregar(_cuenta_id(db, empresa_id, "cta_retencion_sujeto"), retencion, al_debe=False)
        agregar(contrapartida, total, al_debe=False, fecha_vencimiento=documento.fecha_vencimiento)
        tipo_comprobante = TipoComprobante.EGRESO
        origen = OrigenComprobante.COMPRA

    eliminar_asiento_de(db, empresa_id, origen, documento.id)
    comprobante = crear_comprobante(
        db, empresa_id,
        tipo=tipo_comprobante,
        fecha=documento.fecha_emision,
        glosa=glosa,
        lineas=lineas,
        origen=origen,
        origen_id=documento.id,
        usuario=usuario,
        commit=False,
    )
    documento.comprobante_id = comprobante.id
    db.commit()
    return comprobante


def generar_asiento_honorario(
    db: Session, honorario: Honorario, *, cuenta_gasto_id: int | None = None,
    cuenta_pago_id: int | None = None, centro_costo_id: int | None = None,
    usuario: str | None = None,
) -> Comprobante:
    """Asiento de una boleta de honorarios recibida (la empresa retiene) o emitida."""
    empresa_id = honorario.empresa_id
    bruto = pesos(honorario.bruto)
    retencion = pesos(honorario.retencion)
    liquido = pesos(honorario.liquido)
    glosa = f"Boleta honorarios N°{honorario.numero} · {honorario.entidad_nombre}"

    if honorario.tipo == "RECIBIDA":
        lineas = [
            LineaAsiento(
                cuenta_id=cuenta_gasto_id or _cuenta_id(db, empresa_id, "cta_honorarios_gasto"),
                debe=bruto, glosa=glosa, entidad_id=honorario.entidad_id,
                centro_costo_id=centro_costo_id,
            ),
            LineaAsiento(
                cuenta_id=_cuenta_id(db, empresa_id, "cta_retencion_honorarios"),
                haber=retencion, glosa="Retención 2ª categoría",
            ),
            LineaAsiento(
                cuenta_id=cuenta_pago_id or _cuenta_id(db, empresa_id, "cta_honorarios_pagar"),
                haber=liquido, glosa=glosa, entidad_id=honorario.entidad_id,
            ),
        ]
        tipo = TipoComprobante.EGRESO
    else:
        lineas = [
            LineaAsiento(
                cuenta_id=cuenta_pago_id or _cuenta_id(db, empresa_id, "cta_clientes"),
                debe=liquido, glosa=glosa, entidad_id=honorario.entidad_id,
            ),
            LineaAsiento(
                cuenta_id=_cuenta_id(db, empresa_id, "cta_retencion_bte"),
                debe=retencion, glosa="Retención que nos practicaron",
            ),
            LineaAsiento(
                cuenta_id=cuenta_gasto_id or _cuenta_id(db, empresa_id, "cta_ventas_exentas"),
                haber=bruto, glosa=glosa, centro_costo_id=centro_costo_id,
            ),
        ]
        tipo = TipoComprobante.INGRESO

    eliminar_asiento_de(db, empresa_id, OrigenComprobante.HONORARIO, honorario.id)
    comprobante = crear_comprobante(
        db, empresa_id, tipo=tipo, fecha=honorario.fecha, glosa=glosa, lineas=lineas,
        origen=OrigenComprobante.HONORARIO, origen_id=honorario.id, usuario=usuario, commit=False,
    )
    honorario.comprobante_id = comprobante.id
    db.commit()
    return comprobante


def proporcionalidad_iva(db: Session, empresa_id: int) -> float:
    """Porcentaje de IVA de uso común con derecho a crédito (0–1)."""
    valor = valor_parametro(db, empresa_id, "proporcionalidad_iva", "100")
    try:
        return max(0.0, min(1.0, float(valor) / 100))
    except ValueError:
        return 1.0


def registrar_pago_documento(
    db: Session, documento: Documento, *, fecha: date, monto: float, cuenta_pago_id: int,
    usuario: str | None = None,
) -> Comprobante:
    """Asiento de cobro (venta) o pago (compra) contra caja/banco."""
    empresa_id = documento.empresa_id
    es_venta = documento.clase == ClaseDocumento.VENTA
    contra = _cuenta_id(db, empresa_id, "cta_clientes" if es_venta else "cta_proveedores")
    glosa = f"{'Cobro' if es_venta else 'Pago'} documento N°{documento.folio}"
    monto_i = pesos(monto)

    lineas = [
        LineaAsiento(cuenta_id=cuenta_pago_id if es_venta else contra,
                     debe=monto_i, glosa=glosa,
                     entidad_id=None if es_venta else documento.entidad_id,
                     documento_folio=documento.folio),
        LineaAsiento(cuenta_id=contra if es_venta else cuenta_pago_id,
                     haber=monto_i, glosa=glosa,
                     entidad_id=documento.entidad_id if es_venta else None,
                     documento_folio=documento.folio),
    ]
    comprobante = crear_comprobante(
        db, empresa_id,
        tipo=TipoComprobante.INGRESO if es_venta else TipoComprobante.EGRESO,
        fecha=fecha, glosa=glosa, lineas=lineas, usuario=usuario, commit=False,
    )
    if monto_i >= pesos(documento.total):
        documento.pagado = True
    db.commit()
    return comprobante
