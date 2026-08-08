"""Libros de Compras y Ventas (IVA) y sus resúmenes por tipo de documento."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from contaflow.models import ClaseDocumento, Documento, Honorario, TipoCompra, TipoDTE
from contaflow.services.documentos import (
    BOLETAS, BOLETAS_EXENTAS, EXPORTACIONES, FACTURAS_AFECTAS, FACTURAS_COMPRA, FACTURAS_EXENTAS,
    IMPORTACIONES, NOTAS_CREDITO, NOTAS_DEBITO,
)
from contaflow.services.utils import pesos


@dataclass
class ResumenTipo:
    codigo: int
    nombre: str
    cantidad: int = 0
    exento: int = 0
    neto: int = 0
    iva: int = 0
    iva_no_recuperable: int = 0
    impuesto_adicional: int = 0
    retencion: int = 0
    total: int = 0


@dataclass
class Libro:
    clase: ClaseDocumento
    anio: int
    mes: int
    documentos: list[Documento] = field(default_factory=list)
    resumen: dict[int, ResumenTipo] = field(default_factory=dict)

    @property
    def totales(self) -> ResumenTipo:
        t = ResumenTipo(codigo=0, nombre="TOTALES")
        for r in self.resumen.values():
            t.cantidad += r.cantidad
            t.exento += r.exento
            t.neto += r.neto
            t.iva += r.iva
            t.iva_no_recuperable += r.iva_no_recuperable
            t.impuesto_adicional += r.impuesto_adicional
            t.retencion += r.retencion
            t.total += r.total
        return t


def obtener_libro(
    db: Session, empresa_id: int, clase: ClaseDocumento, anio: int, mes: int
) -> Libro:
    """Construye el libro del período con el signo aplicado (NC restan)."""
    documentos = db.scalars(
        select(Documento)
        .where(
            Documento.empresa_id == empresa_id,
            Documento.clase == clase,
            Documento.periodo_anio == anio,
            Documento.periodo_mes == mes,
            Documento.anulado.is_(False),
        )
        .options(joinedload(Documento.tipo), joinedload(Documento.entidad))
        .order_by(Documento.fecha_emision, Documento.tipo_dte, Documento.folio)
    ).unique().all()

    libro = Libro(clase=clase, anio=anio, mes=mes, documentos=list(documentos))
    for doc in documentos:
        signo = doc.tipo.signo if doc.tipo else 1
        item = libro.resumen.setdefault(
            doc.tipo_dte,
            ResumenTipo(codigo=doc.tipo_dte, nombre=doc.tipo.nombre if doc.tipo else str(doc.tipo_dte)),
        )
        item.cantidad += 1
        item.exento += signo * pesos(doc.exento)
        item.neto += signo * pesos(doc.neto)
        item.iva += signo * pesos(doc.iva)
        item.iva_no_recuperable += signo * pesos(doc.iva_no_recuperable)
        item.impuesto_adicional += signo * pesos(doc.impuesto_adicional)
        item.retencion += signo * pesos(doc.retencion)
        item.total += signo * pesos(doc.total)
    return libro


@dataclass
class AgrupacionF29:
    """Montos del período agrupados como los exige el Formulario 29."""

    # Ventas
    facturas_afectas_cant: int = 0
    facturas_afectas_neto: int = 0
    facturas_afectas_iva: int = 0
    facturas_exentas_cant: int = 0
    facturas_exentas_monto: int = 0
    boletas_cant: int = 0
    boletas_neto: int = 0
    boletas_iva: int = 0
    boletas_exentas_cant: int = 0
    boletas_exentas_monto: int = 0
    nc_emitidas_cant: int = 0
    nc_emitidas_neto: int = 0
    nc_emitidas_iva: int = 0
    nd_emitidas_cant: int = 0
    nd_emitidas_neto: int = 0
    nd_emitidas_iva: int = 0
    exportaciones_cant: int = 0
    exportaciones_monto: int = 0
    ventas_retencion: int = 0

    # Compras
    compras_giro_cant: int = 0
    compras_giro_neto: int = 0
    compras_giro_iva: int = 0
    compras_af_cant: int = 0
    compras_af_neto: int = 0
    compras_af_iva: int = 0
    compras_supermercado_cant: int = 0
    compras_supermercado_iva: int = 0
    compras_uso_comun_cant: int = 0
    compras_uso_comun_iva: int = 0
    compras_sin_derecho_cant: int = 0
    compras_sin_derecho_monto: int = 0
    compras_exentas_cant: int = 0
    compras_exentas_monto: int = 0
    nc_recibidas_cant: int = 0
    nc_recibidas_iva: int = 0
    nd_recibidas_cant: int = 0
    nd_recibidas_iva: int = 0
    importaciones_cant: int = 0
    importaciones_iva: int = 0
    compras_retencion: int = 0

    # Honorarios
    honorarios_cant: int = 0
    honorarios_bruto: int = 0
    honorarios_retencion: int = 0


def agrupar_para_f29(db: Session, empresa_id: int, anio: int, mes: int) -> AgrupacionF29:
    """Clasifica los documentos del período en las categorías del F29."""
    g = AgrupacionF29()

    ventas = obtener_libro(db, empresa_id, ClaseDocumento.VENTA, anio, mes)
    for doc in ventas.documentos:
        cod = doc.tipo_dte
        neto, exento, iva = pesos(doc.neto), pesos(doc.exento), pesos(doc.iva)
        g.ventas_retencion += pesos(doc.retencion)
        if cod in NOTAS_CREDITO:
            g.nc_emitidas_cant += 1
            g.nc_emitidas_neto += neto + exento
            g.nc_emitidas_iva += iva
        elif cod in NOTAS_DEBITO:
            g.nd_emitidas_cant += 1
            g.nd_emitidas_neto += neto + exento
            g.nd_emitidas_iva += iva
        elif cod in EXPORTACIONES:
            g.exportaciones_cant += 1
            g.exportaciones_monto += neto + exento
        elif cod in BOLETAS:
            g.boletas_cant += 1
            g.boletas_neto += neto
            g.boletas_iva += iva
        elif cod in BOLETAS_EXENTAS:
            g.boletas_exentas_cant += 1
            g.boletas_exentas_monto += exento + neto
        elif cod in FACTURAS_EXENTAS:
            g.facturas_exentas_cant += 1
            g.facturas_exentas_monto += exento + neto
        else:
            g.facturas_afectas_cant += 1
            g.facturas_afectas_neto += neto
            g.facturas_afectas_iva += iva
            g.facturas_exentas_monto += exento

    compras = obtener_libro(db, empresa_id, ClaseDocumento.COMPRA, anio, mes)
    for doc in compras.documentos:
        cod = doc.tipo_dte
        neto, exento, iva = pesos(doc.neto), pesos(doc.exento), pesos(doc.iva)
        g.compras_retencion += pesos(doc.retencion)
        if cod in NOTAS_CREDITO:
            g.nc_recibidas_cant += 1
            g.nc_recibidas_iva += iva
        elif cod in NOTAS_DEBITO:
            g.nd_recibidas_cant += 1
            g.nd_recibidas_iva += iva
        elif cod in IMPORTACIONES:
            g.importaciones_cant += 1
            g.importaciones_iva += iva
        elif doc.tipo_compra == TipoCompra.ACTIVO_FIJO:
            g.compras_af_cant += 1
            g.compras_af_neto += neto
            g.compras_af_iva += iva
        elif doc.tipo_compra == TipoCompra.SUPERMERCADO:
            g.compras_supermercado_cant += 1
            g.compras_supermercado_iva += iva
            g.compras_giro_neto += neto
        elif doc.tipo_compra == TipoCompra.IVA_USO_COMUN:
            g.compras_uso_comun_cant += 1
            g.compras_uso_comun_iva += iva
            g.compras_giro_neto += neto
        elif doc.tipo_compra == TipoCompra.IVA_NO_RECUPERABLE:
            g.compras_sin_derecho_cant += 1
            g.compras_sin_derecho_monto += pesos(doc.iva_no_recuperable) or iva
            g.compras_giro_neto += neto
        elif cod in FACTURAS_EXENTAS or (not neto and exento):
            g.compras_exentas_cant += 1
            g.compras_exentas_monto += exento
        else:
            g.compras_giro_cant += 1
            g.compras_giro_neto += neto
            g.compras_giro_iva += iva
            g.compras_exentas_monto += exento

    honorarios = db.scalars(
        select(Honorario).where(
            Honorario.empresa_id == empresa_id,
            Honorario.tipo == "RECIBIDA",
            Honorario.periodo_anio == anio,
            Honorario.periodo_mes == mes,
            Honorario.anulado.is_(False),
        )
    ).all()
    for h in honorarios:
        g.honorarios_cant += 1
        g.honorarios_bruto += pesos(h.bruto)
        g.honorarios_retencion += pesos(h.retencion)

    return g


def filas_libro_sii(libro: Libro) -> list[list]:
    """Filas planas del libro, en el orden del CSV que publica el SII."""
    filas = []
    for doc in libro.documentos:
        filas.append([
            doc.tipo_dte,
            doc.tipo.nombre if doc.tipo else "",
            doc.folio,
            doc.fecha_emision.strftime("%d/%m/%Y"),
            doc.entidad_rut,
            doc.entidad_nombre,
            pesos(doc.exento),
            pesos(doc.neto),
            pesos(doc.iva),
            pesos(doc.iva_no_recuperable),
            pesos(doc.impuesto_adicional),
            pesos(doc.retencion),
            pesos(doc.total),
            doc.tipo_compra.value if libro.clase == ClaseDocumento.COMPRA else "",
            doc.ref_tipo_dte or "",
            doc.ref_folio or "",
        ])
    return filas


ENCABEZADO_LIBRO_SII = [
    "Tipo Doc", "Descripción", "Folio", "Fecha Docto", "RUT Contraparte", "Razón Social",
    "Monto Exento", "Monto Neto", "Monto IVA Recuperable", "Monto IVA No Recuperable",
    "Impuesto Adicional", "Retención", "Monto Total", "Tipo Compra",
    "Tipo Doc Referencia", "Folio Referencia",
]
