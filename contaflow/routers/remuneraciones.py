"""Trabajadores, liquidaciones de sueldo, libro de remuneraciones y finiquitos."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.database import get_db
from contaflow.models import (
    AFP, CentroCosto, Liquidacion, TipoContrato, TipoSalud, Trabajador,
)
from contaflow.services.contabilidad import ErrorContable
from contaflow.services.exportar import a_csv, a_excel, a_pdf
from contaflow.services.remuneraciones import (
    EntradaLiquidacion, ErrorRemuneracion, calcular_liquidacion, centralizar_remuneraciones,
    eliminar_liquidacion, finiquito, guardar_liquidacion, libro_remuneraciones,
)
from contaflow.services.utils import (
    formato_moneda, normalizar_rut, parse_fecha, periodo_etiqueta, pesos, rut_valido,
)
from contaflow.web import (
    MIME, decimal, descarga, entero, exigir_empresa, periodo_sesion, redirigir, render,
    usuario_actual,
)

router = APIRouter(prefix="/remuneraciones")


@router.get("/trabajadores")
def trabajadores(request: Request, db: Session = Depends(get_db), texto: str = ""):
    empresa = exigir_empresa(request, db)
    consulta = (
        select(Trabajador)
        .where(Trabajador.empresa_id == empresa.id)
        .order_by(Trabajador.apellidos, Trabajador.nombres)
    )
    if texto:
        consulta = consulta.where(
            Trabajador.nombres.ilike(f"%{texto}%")
            | Trabajador.apellidos.ilike(f"%{texto}%")
            | Trabajador.rut.ilike(f"%{texto}%")
        )
    return render(request, "remuneraciones/trabajadores.html", {
        "lista": db.scalars(consulta).all(),
        "afps": db.scalars(select(AFP).where(AFP.activa.is_(True)).order_by(AFP.nombre)).all(),
        "centros": db.scalars(
            select(CentroCosto).where(CentroCosto.empresa_id == empresa.id)
        ).all(),
        "contratos": list(TipoContrato), "saludes": list(TipoSalud), "texto": texto,
    })


@router.post("/trabajadores/guardar")
async def guardar_trabajador(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    form = await request.form()
    rut = (form.get("rut") or "").strip()
    if not rut_valido(rut):
        return redirigir("/remuneraciones/trabajadores", request,
                         f"El RUT «{rut}» no es válido.", "error")
    rut_norm = normalizar_rut(rut)

    trabajador_id = entero(form.get("trabajador_id"))
    trabajador = db.get(Trabajador, trabajador_id) if trabajador_id else None
    existente = db.scalar(
        select(Trabajador).where(Trabajador.empresa_id == empresa.id, Trabajador.rut == rut_norm)
    )
    if existente and (trabajador is None or existente.id != trabajador.id):
        return redirigir("/remuneraciones/trabajadores", request,
                         f"Ya existe un trabajador con RUT {rut_norm}.", "error")
    if trabajador is None:
        trabajador = Trabajador(empresa_id=empresa.id, rut=rut_norm,
                                fecha_ingreso=date.today(), nombres="", apellidos="")
        db.add(trabajador)

    trabajador.rut = rut_norm
    trabajador.nombres = (form.get("nombres") or "").strip()
    trabajador.apellidos = (form.get("apellidos") or "").strip()
    trabajador.fecha_nacimiento = parse_fecha(form.get("fecha_nacimiento"))
    trabajador.cargo = (form.get("cargo") or "").strip() or None
    trabajador.fecha_ingreso = parse_fecha(form.get("fecha_ingreso"), date.today())
    trabajador.fecha_termino = parse_fecha(form.get("fecha_termino"))
    trabajador.tipo_contrato = TipoContrato(form.get("tipo_contrato", "INDEFINIDO"))
    trabajador.sueldo_base = pesos(decimal(form.get("sueldo_base")))
    trabajador.gratificacion_legal = form.get("gratificacion_legal") == "on"
    trabajador.colacion = pesos(decimal(form.get("colacion")))
    trabajador.movilizacion = pesos(decimal(form.get("movilizacion")))
    trabajador.afp_id = entero(form.get("afp_id")) or None
    trabajador.salud_tipo = TipoSalud(form.get("salud_tipo", "FONASA"))
    trabajador.isapre_nombre = (form.get("isapre_nombre") or "").strip() or None
    trabajador.isapre_plan_uf = decimal(form.get("isapre_plan_uf"))
    trabajador.afecto_afc = form.get("afecto_afc") == "on"
    trabajador.jubilado = form.get("jubilado") == "on"
    trabajador.cargas_familiares = entero(form.get("cargas_familiares"))
    trabajador.asignacion_familiar_tramo = (form.get("tramo") or "D").upper()[:1]
    trabajador.centro_costo_id = entero(form.get("centro_costo_id")) or None
    trabajador.banco = (form.get("banco") or "").strip() or None
    trabajador.cuenta_banco = (form.get("cuenta_banco") or "").strip() or None
    trabajador.activo = form.get("activo", "on") == "on"
    db.commit()
    return redirigir("/remuneraciones/trabajadores", request,
                     f"{trabajador.nombre_completo} guardado.")


# ---------------------------------------------------------------------------
# Liquidaciones
# ---------------------------------------------------------------------------


@router.get("/liquidaciones")
def liquidaciones(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    calculadas = {liq.trabajador_id: liq for liq in libro_remuneraciones(db, empresa.id, anio, mes)}
    activos = db.scalars(
        select(Trabajador)
        .where(Trabajador.empresa_id == empresa.id, Trabajador.activo.is_(True))
        .order_by(Trabajador.apellidos)
    ).all()
    lista = list(calculadas.values())
    return render(request, "remuneraciones/liquidaciones.html", {
        "trabajadores": activos, "calculadas": calculadas, "lista": lista,
        "totales": {
            "imponible": sum(pesos(x.total_imponible) for x in lista),
            "haberes": sum(pesos(x.total_haberes) for x in lista),
            "descuentos": sum(pesos(x.total_descuentos) for x in lista),
            "liquido": sum(pesos(x.liquido) for x in lista),
            "costo": sum(pesos(x.costo_empresa) for x in lista),
        },
    })


@router.post("/liquidaciones/calcular")
async def calcular(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    form = await request.form()
    trabajador = db.get(Trabajador, entero(form.get("trabajador_id")))
    if trabajador is None or trabajador.empresa_id != empresa.id:
        return redirigir("/remuneraciones/liquidaciones", request, "Trabajador no encontrado.", "error")

    entrada = EntradaLiquidacion(
        dias_trabajados=entero(form.get("dias_trabajados"), 30),
        horas_extra=decimal(form.get("horas_extra")),
        bonos=decimal(form.get("bonos")),
        comisiones=decimal(form.get("comisiones")),
        otros_no_imponibles=decimal(form.get("otros_no_imponibles")),
        anticipos=decimal(form.get("anticipos")),
        otros_descuentos=decimal(form.get("otros_descuentos")),
    )
    try:
        liquidacion = calcular_liquidacion(db, trabajador, anio, mes, entrada)
    except ErrorRemuneracion as exc:
        return redirigir("/remuneraciones/liquidaciones", request, str(exc), "error")
    guardar_liquidacion(db, liquidacion)
    return redirigir("/remuneraciones/liquidaciones", request,
                     f"Liquidación de {trabajador.nombre_completo} calculada: "
                     f"líquido {formato_moneda(liquidacion.liquido)}.")


@router.post("/liquidaciones/calcular-todos")
def calcular_todos(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    activos = db.scalars(
        select(Trabajador).where(Trabajador.empresa_id == empresa.id, Trabajador.activo.is_(True))
    ).all()
    procesados = 0
    for trabajador in activos:
        try:
            guardar_liquidacion(
                db, calcular_liquidacion(db, trabajador, anio, mes, EntradaLiquidacion())
            )
            procesados += 1
        except ErrorRemuneracion as exc:
            return redirigir("/remuneraciones/liquidaciones", request, str(exc), "error")
    return redirigir("/remuneraciones/liquidaciones", request,
                     f"{procesados} liquidación(es) calculadas para {periodo_etiqueta(anio, mes)}.")


@router.get("/liquidaciones/{liquidacion_id}")
def ver_liquidacion(liquidacion_id: int, request: Request, db: Session = Depends(get_db),
                    formato: str = ""):
    empresa = exigir_empresa(request, db)
    liq = db.get(Liquidacion, liquidacion_id)
    if liq is None or liq.empresa_id != empresa.id:
        return redirigir("/remuneraciones/liquidaciones", request, "Liquidación no encontrada.", "error")

    if formato == "pdf":
        filas = [
            ["HABERES IMPONIBLES", ""],
            ["Sueldo base", formato_moneda(liq.sueldo_base)],
            ["Gratificación legal", formato_moneda(liq.gratificacion)],
            ["Horas extraordinarias", formato_moneda(liq.horas_extra)],
            ["Bonos", formato_moneda(liq.bonos)],
            ["Comisiones", formato_moneda(liq.comisiones)],
            ["Total imponible", formato_moneda(liq.total_imponible)],
            ["HABERES NO IMPONIBLES", ""],
            ["Colación", formato_moneda(liq.colacion)],
            ["Movilización", formato_moneda(liq.movilizacion)],
            ["Asignación familiar", formato_moneda(liq.asignacion_familiar)],
            ["Otros no imponibles", formato_moneda(liq.otros_no_imponibles)],
            ["TOTAL HABERES", formato_moneda(liq.total_haberes)],
            ["DESCUENTOS", ""],
            [f"AFP ({float(liq.afp_tasa):.2f}%)", formato_moneda(liq.afp_monto)],
            ["Salud 7%", formato_moneda(liq.salud_monto)],
            ["Salud adicional Isapre", formato_moneda(liq.salud_adicional)],
            ["Seguro de cesantía", formato_moneda(liq.afc_monto)],
            ["Impuesto único", formato_moneda(liq.impuesto_unico)],
            ["Anticipos", formato_moneda(liq.anticipos)],
            ["Otros descuentos", formato_moneda(liq.otros_descuentos)],
            ["TOTAL DESCUENTOS", formato_moneda(liq.total_descuentos)],
            ["LÍQUIDO A PAGAR", formato_moneda(liq.liquido)],
        ]
        contenido = a_pdf(
            "Liquidación de Remuneraciones",
            ["Concepto", "Monto"], filas,
            subtitulo=f"{liq.trabajador.nombre_completo} · {liq.trabajador.rut} · "
                      f"{periodo_etiqueta(liq.anio, liq.mes)}",
            empresa=f"{empresa.razon_social} · {empresa.rut}",
            alineacion_derecha={1},
            notas=["Declaro haber recibido conforme el líquido indicado.",
                   "Firma del trabajador: ______________________________"],
        )
        return descarga(contenido, f"liquidacion-{liq.trabajador.rut}-{liq.anio}{liq.mes:02d}.pdf",
                        MIME["pdf"])

    return render(request, "remuneraciones/liquidacion_detalle.html", {"liq": liq})


@router.post("/liquidaciones/{liquidacion_id}/eliminar")
def eliminar(liquidacion_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    liq = db.get(Liquidacion, liquidacion_id)
    if liq is None or liq.empresa_id != empresa.id:
        return redirigir("/remuneraciones/liquidaciones", request, "Liquidación no encontrada.", "error")

    trabajador = liq.trabajador.nombre_completo
    periodo, tenia_asiento = periodo_etiqueta(liq.anio, liq.mes), liq.comprobante_id is not None
    eliminar_liquidacion(db, liq)
    mensaje = f"Liquidación de {trabajador} ({periodo}) eliminada."
    if tenia_asiento:
        mensaje += " Su asiento de centralización también se eliminó — vuelve a centralizar si corresponde."
    return redirigir("/remuneraciones/liquidaciones", request, mensaje)


@router.get("/libro")
def libro(request: Request, db: Session = Depends(get_db), formato: str = ""):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    lista = libro_remuneraciones(db, empresa.id, anio, mes)

    if formato:
        encabezados = [
            "RUT", "Nombre", "Días", "Sueldo base", "Gratificación", "H. Extra", "Bonos",
            "Total imponible", "Colación", "Movilización", "Asig. familiar", "Total haberes",
            "AFP", "Salud", "AFC", "Impuesto único", "Otros desc.", "Total descuentos",
            "Líquido", "SIS", "AFC empleador", "Mutual", "Costo empresa",
        ]
        filas = [[
            liq.trabajador.rut, liq.trabajador.nombre_completo, liq.dias_trabajados,
            pesos(liq.sueldo_base), pesos(liq.gratificacion), pesos(liq.horas_extra),
            pesos(liq.bonos), pesos(liq.total_imponible), pesos(liq.colacion),
            pesos(liq.movilizacion), pesos(liq.asignacion_familiar), pesos(liq.total_haberes),
            pesos(liq.afp_monto), pesos(liq.salud_monto) + pesos(liq.salud_adicional),
            pesos(liq.afc_monto), pesos(liq.impuesto_unico),
            pesos(liq.anticipos) + pesos(liq.otros_descuentos), pesos(liq.total_descuentos),
            pesos(liq.liquido), pesos(liq.sis_empleador), pesos(liq.afc_empleador),
            pesos(liq.mutual), pesos(liq.costo_empresa),
        ] for liq in lista]
        montos = set(range(3, 23))
        nombre = f"libro-remuneraciones-{anio}{mes:02d}"
        if formato == "csv":
            return descarga(a_csv(encabezados, filas), f"{nombre}.csv", MIME["csv"])
        if formato == "pdf":
            filas_pdf = [
                [formato_moneda(v) if i in montos and isinstance(v, int) else v
                 for i, v in enumerate(f)] for f in filas
            ]
            return descarga(
                a_pdf("Libro de Remuneraciones", encabezados, filas_pdf,
                      subtitulo=periodo_etiqueta(anio, mes),
                      empresa=f"{empresa.razon_social} · {empresa.rut}",
                      apaisado=True, alineacion_derecha=montos),
                f"{nombre}.pdf", MIME["pdf"],
            )
        return descarga(
            a_excel("Libro de Remuneraciones", encabezados, filas,
                    subtitulo=f"{empresa.razon_social} · {periodo_etiqueta(anio, mes)}",
                    columnas_monto=montos),
            f"{nombre}.xlsx", MIME["xlsx"],
        )

    return render(request, "remuneraciones/libro.html", {"lista": lista})


@router.post("/centralizar")
def centralizar(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    usuario = usuario_actual(request, db)
    anio, mes = periodo_sesion(request)
    try:
        comp = centralizar_remuneraciones(
            db, empresa.id, anio, mes, usuario.username if usuario else None
        )
    except (ErrorRemuneracion, ErrorContable) as exc:
        return redirigir("/remuneraciones/libro", request, str(exc), "error")
    return redirigir(f"/contabilidad/comprobantes/{comp.id}", request,
                     f"Remuneraciones centralizadas en el comprobante {comp.folio}.")


# ---------------------------------------------------------------------------
# Finiquito
# ---------------------------------------------------------------------------


@router.get("/finiquito")
def calculadora_finiquito(request: Request, db: Session = Depends(get_db),
                          trabajador_id: int = 0, fecha_termino: str = "",
                          ultima_remuneracion: str = "", dias_vacaciones: str = "",
                          con_indemnizacion: str = "on"):
    empresa = exigir_empresa(request, db)
    trabajadores = db.scalars(
        select(Trabajador).where(Trabajador.empresa_id == empresa.id).order_by(Trabajador.apellidos)
    ).all()
    resultado, trabajador = None, None
    if trabajador_id:
        trabajador = db.get(Trabajador, trabajador_id)
        if trabajador and trabajador.empresa_id == empresa.id:
            resultado = finiquito(
                trabajador,
                parse_fecha(fecha_termino, date.today()),
                decimal(ultima_remuneracion) or float(trabajador.sueldo_base),
                decimal(dias_vacaciones),
                con_indemnizacion == "on",
            )
    return render(request, "remuneraciones/finiquito.html", {
        "trabajadores": trabajadores, "trabajador": trabajador, "resultado": resultado,
        "fecha_termino": fecha_termino, "ultima_remuneracion": ultima_remuneracion,
        "dias_vacaciones": dias_vacaciones, "con_indemnizacion": con_indemnizacion,
    })
