"""Compras, ventas, honorarios, libros de IVA y propuestas de formularios."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.database import get_db
from contaflow.models import (
    CentroCosto, ClaseDocumento, Cuenta, Documento, Entidad, Honorario, TipoCompra, TipoDTE,
)
from contaflow.services.contabilidad import ErrorContable, capturar_integridad
from contaflow.services.documentos import (
    calcular_iva, generar_asiento_documento, generar_asiento_honorario, neto_desde_total,
    obtener_o_crear_entidad, totalizar,
)
from contaflow.services.exportar import a_csv, a_excel, a_pdf, pdf_formulario
from contaflow.services.formularios import (
    generar_f22, generar_f29, guardar_f22, guardar_f29, tasa_retencion_honorarios,
)
from contaflow.services.libros import ENCABEZADO_LIBRO_SII, filas_libro_sii, obtener_libro
from contaflow.services.utils import (
    formato_fecha, formato_moneda, normalizar_rut, parse_fecha, periodo_etiqueta, pesos,
    rut_valido, slug,
)
from contaflow.web import (
    MIME, decimal, descarga, entero, exigir_empresa, periodo_sesion, redirigir, render,
    usuario_actual,
)

router = APIRouter(prefix="/tributario")


def _tipos_dte(db: Session, clase: ClaseDocumento) -> list[TipoDTE]:
    campo = TipoDTE.es_venta if clase == ClaseDocumento.VENTA else TipoDTE.es_compra
    return list(db.scalars(select(TipoDTE).where(campo.is_(True)).order_by(TipoDTE.codigo)).all())


def _contexto_documento(db: Session, empresa_id: int, clase: ClaseDocumento) -> dict:
    return {
        "clase": clase,
        "tipos": _tipos_dte(db, clase),
        "entidades": db.scalars(
            select(Entidad).where(Entidad.empresa_id == empresa_id, Entidad.activo.is_(True))
            .order_by(Entidad.razon_social)
        ).all(),
        "cuentas": db.scalars(
            select(Cuenta).where(
                Cuenta.empresa_id == empresa_id, Cuenta.imputable.is_(True), Cuenta.activa.is_(True)
            ).order_by(Cuenta.codigo)
        ).all(),
        "centros": db.scalars(
            select(CentroCosto).where(CentroCosto.empresa_id == empresa_id).order_by(CentroCosto.codigo)
        ).all(),
        "tipos_compra": list(TipoCompra),
    }


# ---------------------------------------------------------------------------
# Documentos
# ---------------------------------------------------------------------------


@router.get("/ventas")
def ventas(request: Request, db: Session = Depends(get_db)):
    return _lista_documentos(request, db, ClaseDocumento.VENTA)


@router.get("/compras")
def compras(request: Request, db: Session = Depends(get_db)):
    return _lista_documentos(request, db, ClaseDocumento.COMPRA)


def _lista_documentos(request: Request, db: Session, clase: ClaseDocumento):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    libro = obtener_libro(db, empresa.id, clase, anio, mes)
    return render(request, "tributario/documentos.html", {
        "libro": libro, "clase": clase,
        "titulo": "Libro de Ventas" if clase == ClaseDocumento.VENTA else "Libro de Compras",
        "ruta": "ventas" if clase == ClaseDocumento.VENTA else "compras",
    })


@router.get("/documentos/{ruta}/nuevo")
def nuevo_documento(ruta: str, request: Request, db: Session = Depends(get_db)):
    if ruta not in ("ventas", "compras"):
        return redirigir("/", request, "Sección no encontrada.", "error")
    empresa = exigir_empresa(request, db)
    clase = ClaseDocumento.VENTA if ruta == "ventas" else ClaseDocumento.COMPRA
    anio, mes = periodo_sesion(request)
    ctx = _contexto_documento(db, empresa.id, clase)
    ctx.update(registro=None, ruta=ruta, anio=anio, mes=mes, fecha_hoy=date.today())
    return render(request, "tributario/documento_form.html", ctx)


@router.post("/documentos/{ruta}/guardar")
async def guardar_documento(ruta: str, request: Request, db: Session = Depends(get_db)):
    if ruta not in ("ventas", "compras"):
        return redirigir("/", request, "Sección no encontrada.", "error")
    empresa = exigir_empresa(request, db)
    usuario = usuario_actual(request, db)
    clase = ClaseDocumento.VENTA if ruta == "ventas" else ClaseDocumento.COMPRA
    form = await request.form()

    rut = (form.get("entidad_rut") or "").strip()
    if not rut_valido(rut):
        return redirigir(f"/tributario/documentos/{ruta}/nuevo", request,
                         f"El RUT «{rut}» no es válido (dígito verificador incorrecto).", "error")

    entidad = obtener_o_crear_entidad(
        db, empresa.id, rut, (form.get("entidad_nombre") or "").strip() or "Sin nombre",
        cliente=clase == ClaseDocumento.VENTA, proveedor=clase == ClaseDocumento.COMPRA,
    )

    tipo_dte = entero(form.get("tipo_dte"), 33)
    tipo = db.get(TipoDTE, tipo_dte)
    modo = form.get("modo_monto", "neto")

    if modo == "total" and tipo and tipo.afecto_iva:
        # Boletas: el monto viene con IVA incluido.
        total_bruto = decimal(form.get("total_bruto"))
        neto = neto_desde_total(total_bruto)
        iva = pesos(total_bruto) - neto
        exento = decimal(form.get("exento"))
    else:
        neto = decimal(form.get("neto"))
        exento = decimal(form.get("exento"))
        iva_manual = form.get("iva")
        iva = pesos(iva_manual) if iva_manual not in (None, "") else (
            calcular_iva(neto) if (tipo and tipo.afecto_iva) else 0
        )

    montos = totalizar(
        neto=neto, exento=exento, iva=iva,
        impuesto_adicional=decimal(form.get("impuesto_adicional")),
        retencion=decimal(form.get("retencion")),
        iva_no_recuperable=decimal(form.get("iva_no_recuperable")),
    )

    fecha_emision = parse_fecha(form.get("fecha_emision"), date.today())
    anio_p = entero(form.get("periodo_anio"), fecha_emision.year)
    mes_p = entero(form.get("periodo_mes"), fecha_emision.month)

    documento_id = entero(form.get("documento_id"))
    documento = db.get(Documento, documento_id) if documento_id else None
    if documento is None:
        documento = Documento(empresa_id=empresa.id, clase=clase)
        db.add(documento)

    documento.tipo_dte = tipo_dte
    documento.folio = (form.get("folio") or "").strip()
    documento.fecha_emision = fecha_emision
    documento.fecha_vencimiento = parse_fecha(form.get("fecha_vencimiento"))
    documento.periodo_anio = anio_p
    documento.periodo_mes = mes_p
    documento.entidad_id = entidad.id
    documento.entidad_rut = normalizar_rut(rut)
    documento.entidad_nombre = entidad.razon_social
    documento.neto = montos["neto"]
    documento.exento = montos["exento"]
    documento.iva = montos["iva"]
    documento.iva_no_recuperable = montos["iva_no_recuperable"]
    documento.impuesto_adicional = montos["impuesto_adicional"]
    documento.retencion = montos["retencion"]
    documento.total = montos["total"]
    documento.tipo_compra = TipoCompra(form.get("tipo_compra", TipoCompra.DEL_GIRO.value))
    documento.ref_tipo_dte = entero(form.get("ref_tipo_dte")) or None
    documento.ref_folio = (form.get("ref_folio") or "").strip() or None
    documento.ref_fecha = parse_fecha(form.get("ref_fecha"))
    documento.ref_razon = (form.get("ref_razon") or "").strip() or None
    documento.observacion = (form.get("observacion") or "").strip() or None
    mensaje_choque = (
        f"Ya existe un documento tipo {tipo_dte} folio {documento.folio} para "
        f"{documento.entidad_rut} en esta empresa. Revisa si ya estaba cargado."
    )
    try:
        with capturar_integridad(db, mensaje_choque):
            db.commit()
    except ErrorContable as exc:
        return redirigir(f"/tributario/documentos/{ruta}/nuevo", request, str(exc), "error")

    if form.get("contabilizar", "on") == "on":
        try:
            generar_asiento_documento(
                db, documento,
                cuenta_contrapartida_id=entero(form.get("cuenta_contrapartida")) or None,
                cuenta_resultado_id=entero(form.get("cuenta_resultado")) or None,
                centro_costo_id=entero(form.get("centro_costo")) or None,
                usuario=usuario.username if usuario else None,
            )
        except ErrorContable as exc:
            return redirigir(f"/tributario/{ruta}", request,
                             f"Documento guardado, pero no se contabilizó: {exc}", "warn")

    return redirigir(f"/tributario/{ruta}", request,
                     f"Documento {documento.folio} registrado y contabilizado.")


@router.post("/documentos/{documento_id}/anular")
def anular_documento(documento_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    documento = db.get(Documento, documento_id)
    if documento is None or documento.empresa_id != empresa.id:
        return redirigir("/", request, "Documento no encontrado.", "error")
    documento.anulado = True
    ruta = "ventas" if documento.clase == ClaseDocumento.VENTA else "compras"
    from contaflow.models import OrigenComprobante
    from contaflow.services.contabilidad import eliminar_asiento_de

    origen = (OrigenComprobante.VENTA if documento.clase == ClaseDocumento.VENTA
              else OrigenComprobante.COMPRA)
    eliminar_asiento_de(db, empresa.id, origen, documento.id)
    documento.comprobante_id = None
    db.commit()
    return redirigir(f"/tributario/{ruta}", request,
                     f"Documento {documento.folio} anulado y su asiento eliminado.")


# ---------------------------------------------------------------------------
# Libros de IVA
# ---------------------------------------------------------------------------


@router.get("/libro/{ruta}")
def exportar_libro(ruta: str, request: Request, db: Session = Depends(get_db), formato: str = "xlsx"):
    empresa = exigir_empresa(request, db)
    clase = ClaseDocumento.VENTA if ruta == "ventas" else ClaseDocumento.COMPRA
    anio, mes = periodo_sesion(request)
    libro = obtener_libro(db, empresa.id, clase, anio, mes)
    filas = filas_libro_sii(libro)
    titulo = f"Libro de {'Ventas' if clase == ClaseDocumento.VENTA else 'Compras'}"
    subtitulo = periodo_etiqueta(anio, mes)
    nombre = f"{slug(titulo)}-{anio}{mes:02d}"
    montos = {6, 7, 8, 9, 10, 11, 12}

    if formato == "csv":
        return descarga(a_csv(ENCABEZADO_LIBRO_SII, filas), f"{nombre}.csv", MIME["csv"])
    if formato == "pdf":
        filas_pdf = [
            [formato_moneda(v) if i in montos and isinstance(v, int) else v
             for i, v in enumerate(f)]
            for f in filas
        ]
        return descarga(
            a_pdf(titulo, ENCABEZADO_LIBRO_SII, filas_pdf, subtitulo=subtitulo,
                  empresa=f"{empresa.razon_social} · {empresa.rut}", apaisado=True,
                  alineacion_derecha=montos),
            f"{nombre}.pdf", MIME["pdf"],
        )

    resumen = [
        [r.codigo, r.nombre, r.cantidad, r.exento, r.neto, r.iva, r.impuesto_adicional, r.total]
        for r in libro.resumen.values()
    ]
    t = libro.totales
    resumen.append(["", "TOTALES", t.cantidad, t.exento, t.neto, t.iva, t.impuesto_adicional, t.total])
    return descarga(
        a_excel(
            titulo, ENCABEZADO_LIBRO_SII, filas,
            subtitulo=f"{empresa.razon_social} · {subtitulo}", columnas_monto=montos,
            hojas_extra=[("Resumen", ["Tipo", "Documento", "Cantidad", "Exento", "Neto", "IVA",
                                      "Imp. Adicional", "Total"], resumen)],
        ),
        f"{nombre}.xlsx", MIME["xlsx"],
    )


# ---------------------------------------------------------------------------
# Honorarios
# ---------------------------------------------------------------------------


@router.get("/honorarios")
def honorarios(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    lista = db.scalars(
        select(Honorario).where(
            Honorario.empresa_id == empresa.id,
            Honorario.periodo_anio == anio,
            Honorario.periodo_mes == mes,
        ).order_by(Honorario.fecha)
    ).all()
    return render(request, "tributario/honorarios.html", {
        "lista": lista,
        "tasa": tasa_retencion_honorarios(anio),
        "total_bruto": sum(pesos(h.bruto) for h in lista if not h.anulado),
        "total_retencion": sum(pesos(h.retencion) for h in lista if not h.anulado),
        "entidades": db.scalars(
            select(Entidad).where(Entidad.empresa_id == empresa.id).order_by(Entidad.razon_social)
        ).all(),
        "cuentas": db.scalars(
            select(Cuenta).where(Cuenta.empresa_id == empresa.id, Cuenta.imputable.is_(True))
            .order_by(Cuenta.codigo)
        ).all(),
    })


@router.post("/honorarios/guardar")
async def guardar_honorario(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    usuario = usuario_actual(request, db)
    form = await request.form()
    anio, mes = periodo_sesion(request)

    rut = (form.get("entidad_rut") or "").strip()
    if not rut_valido(rut):
        return redirigir("/tributario/honorarios", request, f"RUT «{rut}» inválido.", "error")

    fecha = parse_fecha(form.get("fecha"), date.today())
    bruto = pesos(decimal(form.get("bruto")))
    tasa = decimal(form.get("tasa"), tasa_retencion_honorarios(fecha.year) * 100) / 100
    retencion = pesos(bruto * tasa)

    entidad = obtener_o_crear_entidad(
        db, empresa.id, rut, (form.get("entidad_nombre") or "Profesional").strip(), proveedor=True
    )
    honorario = Honorario(
        empresa_id=empresa.id,
        tipo=form.get("tipo", "RECIBIDA"),
        numero=(form.get("numero") or "").strip(),
        fecha=fecha,
        periodo_anio=entero(form.get("periodo_anio"), anio),
        periodo_mes=entero(form.get("periodo_mes"), mes),
        entidad_id=entidad.id,
        entidad_rut=normalizar_rut(rut),
        entidad_nombre=entidad.razon_social,
        bruto=bruto, tasa_retencion=tasa, retencion=retencion, liquido=bruto - retencion,
        glosa=(form.get("glosa") or "").strip() or None,
    )
    db.add(honorario)
    db.commit()

    try:
        generar_asiento_honorario(
            db, honorario,
            cuenta_gasto_id=entero(form.get("cuenta_gasto")) or None,
            usuario=usuario.username if usuario else None,
        )
    except ErrorContable as exc:
        return redirigir("/tributario/honorarios", request,
                         f"Boleta guardada, pero no se contabilizó: {exc}", "warn")
    return redirigir("/tributario/honorarios", request,
                     f"Boleta de honorarios N°{honorario.numero} registrada.")


@router.post("/honorarios/{honorario_id}/anular")
def anular_honorario(honorario_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    honorario = db.get(Honorario, honorario_id)
    if honorario is None or honorario.empresa_id != empresa.id:
        return redirigir("/tributario/honorarios", request, "Boleta no encontrada.", "error")
    from contaflow.models import OrigenComprobante
    from contaflow.services.contabilidad import eliminar_asiento_de

    honorario.anulado = True
    eliminar_asiento_de(db, empresa.id, OrigenComprobante.HONORARIO, honorario.id)
    db.commit()
    return redirigir("/tributario/honorarios", request, "Boleta anulada.")


# ---------------------------------------------------------------------------
# Formulario 29
# ---------------------------------------------------------------------------


@router.get("/f29")
def f29(request: Request, db: Session = Depends(get_db), formato: str = "",
        remanente: str = "", ppm_tasa: str = "", sence: str = ""):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    prop = generar_f29(
        db, empresa, anio, mes,
        remanente_anterior=pesos(decimal(remanente)) if remanente != "" else None,
        ppm_tasa=decimal(ppm_tasa) if ppm_tasa != "" else None,
        creditos_sence=pesos(decimal(sence)),
    )

    if formato:
        return _exportar_formulario(formato, prop, empresa, "F29", periodo_etiqueta(anio, mes), [
            ("IVA determinado", formato_moneda(prop.iva_determinado)),
            ("Remanente período siguiente (cód. 77)", formato_moneda(prop.remanente_siguiente)),
            ("TOTAL A PAGAR (cód. 91)", formato_moneda(prop.total_a_pagar)),
        ])

    return render(request, "tributario/f29.html", {
        "prop": prop, "secciones": prop.por_seccion(),
        "remanente": remanente, "ppm_tasa": ppm_tasa, "sence": sence,
    })


@router.post("/f29/guardar")
def guardar_declaracion_f29(
    request: Request, db: Session = Depends(get_db),
    remanente: str = Form(""), ppm_tasa: str = Form(""), sence: str = Form(""),
):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    prop = generar_f29(
        db, empresa, anio, mes,
        remanente_anterior=pesos(decimal(remanente)) if remanente != "" else None,
        ppm_tasa=decimal(ppm_tasa) if ppm_tasa != "" else None,
        creditos_sence=pesos(decimal(sence)),
    )
    guardar_f29(db, empresa.id, prop)
    return redirigir("/tributario/f29", request,
                     f"F29 de {periodo_etiqueta(anio, mes)} guardado. "
                     f"El remanente quedará disponible para el mes siguiente.")


# ---------------------------------------------------------------------------
# Formulario 22
# ---------------------------------------------------------------------------


@router.get("/f22")
def f22(request: Request, db: Session = Depends(get_db), formato: str = "", anio: int = 0,
        agregados: str = "", deducciones: str = "", perdida: str = "", ppm: str = "",
        creditos: str = ""):
    empresa = exigir_empresa(request, db)
    anio_activo, _ = periodo_sesion(request)
    anio = anio or anio_activo
    prop = generar_f22(
        db, empresa, anio,
        agregados=pesos(decimal(agregados)),
        deducciones=pesos(decimal(deducciones)),
        perdida_ejercicios_anteriores=pesos(decimal(perdida)),
        ppm_pagados=pesos(decimal(ppm)),
        creditos_impuesto=pesos(decimal(creditos)),
    )
    if formato:
        return _exportar_formulario(formato, prop, empresa, "F22", f"Año comercial {anio}", [
            ("Renta Líquida Imponible", formato_moneda(prop.rli)),
            ("Impuesto Primera Categoría", formato_moneda(prop.impuesto_primera)),
            ("Saldo a pagar / devolver", formato_moneda(prop.saldo)),
        ])
    return render(request, "tributario/f22.html", {
        "prop": prop, "secciones": prop.por_seccion(), "anio": anio,
        "agregados": agregados, "deducciones": deducciones, "perdida": perdida,
        "ppm": ppm, "creditos": creditos,
    })


def _exportar_formulario(formato: str, prop, empresa, nombre_form: str, periodo: str,
                         resumen: list[tuple[str, str]]):
    titulo = f"Propuesta Formulario {nombre_form[1:]}"
    nombre = f"{nombre_form.lower()}-{slug(empresa.rut)}-{slug(periodo)}"
    encabezados = ["Sección", "Código", "Concepto", "Valor", "Nota"]
    filas = [[c.seccion, c.codigo, c.etiqueta, c.valor, c.nota] for c in prop.codigos]

    if formato == "csv":
        return descarga(a_csv(encabezados, filas), f"{nombre}.csv", MIME["csv"])
    if formato == "xlsx":
        return descarga(
            a_excel(titulo, encabezados, filas,
                    subtitulo=f"{empresa.razon_social} · {periodo}", columnas_monto={3},
                    hojas_extra=[("Resumen", ["Concepto", "Valor"], [list(r) for r in resumen])]),
            f"{nombre}.xlsx", MIME["xlsx"],
        )
    return descarga(
        pdf_formulario(titulo, f"{empresa.razon_social} · {empresa.rut}", periodo,
                       prop.por_seccion(), resumen=resumen, notas=prop.advertencias),
        f"{nombre}.pdf", MIME["pdf"],
    )
