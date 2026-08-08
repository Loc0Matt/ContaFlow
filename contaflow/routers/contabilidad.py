"""Comprobantes, libro diario, libro mayor, balance y control de períodos."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from contaflow.database import get_db
from contaflow.models import (
    CentroCosto, Comprobante, Cuenta, Entidad, EstadoComprobante, EstadoPeriodo, Movimiento,
    Periodo, TipoComprobante,
)
from contaflow.services.contabilidad import (
    ErrorContable, LineaAsiento, anular_comprobante, cerrar_ejercicio, crear_comprobante,
    libro_diario, libro_mayor, saldos,
)
from contaflow.services.exportar import a_csv, a_excel, a_pdf
from contaflow.services.seed import cuenta_parametro
from contaflow.services.utils import (
    formato_fecha, formato_moneda, parse_fecha, pesos, periodo_etiqueta, rango_mes,
)
from contaflow.web import (
    MIME, decimal, descarga, entero, exigir_empresa, periodo_sesion, redirigir, render,
    usuario_actual,
)

router = APIRouter(prefix="/contabilidad")


def _cuentas_imputables(db: Session, empresa_id: int) -> list[Cuenta]:
    return list(db.scalars(
        select(Cuenta)
        .where(Cuenta.empresa_id == empresa_id, Cuenta.imputable.is_(True), Cuenta.activa.is_(True))
        .order_by(Cuenta.codigo)
    ).all())


def _contexto_asiento(db: Session, empresa_id: int) -> dict:
    return {
        "cuentas": _cuentas_imputables(db, empresa_id),
        "entidades": db.scalars(
            select(Entidad).where(Entidad.empresa_id == empresa_id, Entidad.activo.is_(True))
            .order_by(Entidad.razon_social)
        ).all(),
        "centros": db.scalars(
            select(CentroCosto).where(CentroCosto.empresa_id == empresa_id, CentroCosto.activo.is_(True))
            .order_by(CentroCosto.codigo)
        ).all(),
        "tipos": list(TipoComprobante),
    }


# ---------------------------------------------------------------------------
# Comprobantes
# ---------------------------------------------------------------------------


@router.get("/comprobantes")
def lista_comprobantes(
    request: Request, db: Session = Depends(get_db),
    desde: str = "", hasta: str = "", tipo: str = "", texto: str = "",
):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    ini, fin = rango_mes(anio, mes)
    f_desde = parse_fecha(desde, ini)
    f_hasta = parse_fecha(hasta, fin)

    consulta = (
        select(Comprobante)
        .where(
            Comprobante.empresa_id == empresa.id,
            Comprobante.fecha >= f_desde,
            Comprobante.fecha <= f_hasta,
        )
        .order_by(Comprobante.fecha.desc(), Comprobante.id.desc())
    )
    if tipo:
        consulta = consulta.where(Comprobante.tipo == TipoComprobante(tipo))
    if texto:
        consulta = consulta.where(Comprobante.glosa.ilike(f"%{texto}%"))

    return render(request, "contabilidad/comprobantes.html", {
        "lista": db.scalars(consulta).all(),
        "desde": f_desde, "hasta": f_hasta, "tipo": tipo, "texto": texto,
        "tipos": list(TipoComprobante),
    })


@router.get("/comprobantes/nuevo")
def nuevo_comprobante(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    _, fin = rango_mes(anio, mes)
    ctx = _contexto_asiento(db, empresa.id)
    ctx.update(registro=None, fecha_sugerida=min(fin, date.today()))
    return render(request, "contabilidad/asiento_form.html", ctx)


@router.post("/comprobantes/guardar")
async def guardar_comprobante(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    usuario = usuario_actual(request, db)
    form = await request.form()

    lineas: list[LineaAsiento] = []
    indices = sorted({
        k.split("_")[-1] for k in form.keys() if k.startswith("cuenta_id_")
    }, key=lambda x: int(x) if x.isdigit() else 0)
    for i in indices:
        cuenta_id = entero(form.get(f"cuenta_id_{i}"))
        if not cuenta_id:
            continue
        lineas.append(LineaAsiento(
            cuenta_id=cuenta_id,
            debe=decimal(form.get(f"debe_{i}")),
            haber=decimal(form.get(f"haber_{i}")),
            glosa=(form.get(f"glosa_{i}") or "").strip() or None,
            centro_costo_id=entero(form.get(f"centro_{i}")) or None,
            entidad_id=entero(form.get(f"entidad_{i}")) or None,
            documento_folio=(form.get(f"folio_{i}") or "").strip() or None,
            fecha_vencimiento=parse_fecha(form.get(f"vencimiento_{i}")),
        ))

    try:
        comprobante = crear_comprobante(
            db, empresa.id,
            tipo=TipoComprobante(form.get("tipo", "TRASPASO")),
            fecha=parse_fecha(form.get("fecha"), date.today()),
            glosa=(form.get("glosa") or "Asiento contable").strip(),
            lineas=lineas,
            estado=EstadoComprobante.CONTABILIZADO
            if form.get("estado", "CONTABILIZADO") == "CONTABILIZADO"
            else EstadoComprobante.BORRADOR,
            usuario=usuario.username if usuario else None,
            observacion=(form.get("observacion") or "").strip() or None,
        )
    except ErrorContable as exc:
        return redirigir("/contabilidad/comprobantes/nuevo", request, str(exc), "error")

    return redirigir(
        f"/contabilidad/comprobantes/{comprobante.id}", request,
        f"Comprobante {comprobante.folio} registrado.",
    )


@router.get("/comprobantes/{comprobante_id}")
def ver_comprobante(comprobante_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    comprobante = db.scalar(
        select(Comprobante)
        .where(Comprobante.id == comprobante_id, Comprobante.empresa_id == empresa.id)
        .options(joinedload(Comprobante.lineas).joinedload(Movimiento.cuenta))
    )
    if comprobante is None:
        return redirigir("/contabilidad/comprobantes", request, "Comprobante no encontrado.", "error")
    return render(request, "contabilidad/asiento_detalle.html", {"registro": comprobante})


@router.post("/comprobantes/{comprobante_id}/anular")
def anular(comprobante_id: int, request: Request, motivo: str = Form(""),
           db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    comprobante = db.scalar(
        select(Comprobante).where(
            Comprobante.id == comprobante_id, Comprobante.empresa_id == empresa.id
        )
    )
    if comprobante is None:
        return redirigir("/contabilidad/comprobantes", request, "Comprobante no encontrado.", "error")
    try:
        anular_comprobante(db, comprobante, motivo)
    except ErrorContable as exc:
        return redirigir(f"/contabilidad/comprobantes/{comprobante_id}", request, str(exc), "error")
    return redirigir("/contabilidad/comprobantes", request, f"Comprobante {comprobante.folio} anulado.")


# ---------------------------------------------------------------------------
# Libro diario
# ---------------------------------------------------------------------------


@router.get("/diario")
def diario(request: Request, db: Session = Depends(get_db), formato: str = "", tipo: str = ""):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    desde, hasta = rango_mes(anio, mes)
    comprobantes = libro_diario(
        db, empresa.id, desde, hasta, TipoComprobante(tipo) if tipo else None
    )

    if formato:
        encabezados = ["Fecha", "Comprobante", "Cuenta", "Nombre cuenta", "Glosa", "Debe", "Haber"]
        filas = []
        for comp in comprobantes:
            for mov in comp.lineas:
                filas.append([
                    formato_fecha(comp.fecha), comp.folio, mov.cuenta.codigo, mov.cuenta.nombre,
                    mov.glosa or comp.glosa, pesos(mov.debe), pesos(mov.haber),
                ])
        return _exportar(
            formato, "Libro Diario", encabezados, filas, empresa,
            f"Período {periodo_etiqueta(anio, mes)}", {5, 6},
        )

    total_debe = sum(pesos(c.total_debe) for c in comprobantes)
    total_haber = sum(pesos(c.total_haber) for c in comprobantes)
    return render(request, "contabilidad/diario.html", {
        "comprobantes": comprobantes, "total_debe": total_debe, "total_haber": total_haber,
        "tipo": tipo, "tipos": list(TipoComprobante),
    })


# ---------------------------------------------------------------------------
# Libro mayor
# ---------------------------------------------------------------------------


@router.get("/mayor")
def mayor(request: Request, db: Session = Depends(get_db), cuenta_id: int = 0,
          desde: str = "", hasta: str = "", formato: str = ""):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    ini, fin = rango_mes(anio, mes)
    f_desde = parse_fecha(desde, date(anio, 1, 1))
    f_hasta = parse_fecha(hasta, fin)

    cuentas = _cuentas_imputables(db, empresa.id)
    saldo_anterior, filas = (0.0, [])
    cuenta = db.get(Cuenta, cuenta_id) if cuenta_id else None
    if cuenta is not None and cuenta.empresa_id == empresa.id:
        saldo_anterior, filas = libro_mayor(db, empresa.id, cuenta.id, f_desde, f_hasta)

    if formato and cuenta is not None:
        encabezados = ["Fecha", "Comprobante", "Glosa", "Documento", "Debe", "Haber", "Saldo"]
        datos = [["", "", "SALDO ANTERIOR", "", 0, 0, pesos(saldo_anterior)]]
        for mov, acumulado in filas:
            datos.append([
                formato_fecha(mov.comprobante.fecha), mov.comprobante.folio, mov.glosa or "",
                mov.documento_folio or "", pesos(mov.debe), pesos(mov.haber), pesos(acumulado),
            ])
        return _exportar(
            formato, f"Libro Mayor {cuenta.codigo}", encabezados, datos, empresa,
            f"{cuenta.nombre} · {formato_fecha(f_desde)} a {formato_fecha(f_hasta)}", {4, 5, 6},
        )

    return render(request, "contabilidad/mayor.html", {
        "cuentas": cuentas, "cuenta": cuenta, "filas": filas,
        "saldo_anterior": saldo_anterior, "desde": f_desde, "hasta": f_hasta,
        "total_debe": sum(pesos(m.debe) for m, _ in filas),
        "total_haber": sum(pesos(m.haber) for m, _ in filas),
    })


# ---------------------------------------------------------------------------
# Balance de comprobación y saldos (8 columnas)
# ---------------------------------------------------------------------------


@router.get("/balance")
def balance_ocho_columnas(request: Request, db: Session = Depends(get_db), formato: str = "",
                          hasta_mes: int = 0):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    mes_corte = hasta_mes or mes
    inicio = date(anio, 1, 1)
    _, hasta = rango_mes(anio, mes_corte)
    desde, _ = rango_mes(anio, mes_corte)

    filas = saldos(db, empresa.id, desde=desde, hasta=hasta, inicio_ejercicio=inicio)
    totales = {
        "debe": sum(f.debe_acumulado for f in filas),
        "haber": sum(f.haber_acumulado for f in filas),
        "deudor": sum(f.saldo_deudor for f in filas),
        "acreedor": sum(f.saldo_acreedor for f in filas),
        "activo": sum(f.activo for f in filas),
        "pasivo": sum(f.pasivo for f in filas),
        "perdida": sum(f.perdida for f in filas),
        "ganancia": sum(f.ganancia for f in filas),
    }
    resultado = totales["ganancia"] - totales["perdida"]

    if formato:
        encabezados = [
            "Código", "Cuenta", "Debe", "Haber", "Saldo Deudor", "Saldo Acreedor",
            "Activo", "Pasivo", "Pérdida", "Ganancia",
        ]
        datos = [
            [f.cuenta.codigo, f.cuenta.nombre, pesos(f.debe_acumulado), pesos(f.haber_acumulado),
             pesos(f.saldo_deudor), pesos(f.saldo_acreedor), pesos(f.activo), pesos(f.pasivo),
             pesos(f.perdida), pesos(f.ganancia)]
            for f in filas
        ]
        datos.append(["", "TOTALES"] + [pesos(v) for v in totales.values()])
        return _exportar(
            formato, "Balance de Comprobación y Saldos", encabezados, datos, empresa,
            f"Acumulado a {periodo_etiqueta(anio, mes_corte)}", set(range(2, 10)), apaisado=True,
        )

    return render(request, "contabilidad/balance.html", {
        "filas": filas, "totales": totales, "resultado": resultado, "mes_corte": mes_corte,
    })


# ---------------------------------------------------------------------------
# Períodos y cierre
# ---------------------------------------------------------------------------


@router.get("/periodos")
def periodos(request: Request, db: Session = Depends(get_db), anio: int = 0):
    empresa = exigir_empresa(request, db)
    anio_activo, _ = periodo_sesion(request)
    anio = anio or anio_activo
    existentes = {
        p.mes: p for p in db.scalars(
            select(Periodo).where(Periodo.empresa_id == empresa.id, Periodo.anio == anio)
        ).all()
    }
    cuenta_resultado = cuenta_parametro(db, empresa.id, "cta_resultado")
    return render(request, "contabilidad/periodos.html", {
        "anio": anio, "periodos": existentes, "cuenta_resultado": cuenta_resultado,
    })


@router.post("/periodos/cambiar")
def cambiar_periodo(
    request: Request, anio: int = Form(...), mes: int = Form(...), db: Session = Depends(get_db)
):
    empresa = exigir_empresa(request, db)
    periodo = db.scalar(
        select(Periodo).where(
            Periodo.empresa_id == empresa.id, Periodo.anio == anio, Periodo.mes == mes
        )
    )
    if periodo is None:
        periodo = Periodo(empresa_id=empresa.id, anio=anio, mes=mes, estado=EstadoPeriodo.CERRADO)
        db.add(periodo)
    else:
        periodo.estado = (
            EstadoPeriodo.ABIERTO if periodo.estado == EstadoPeriodo.CERRADO
            else EstadoPeriodo.CERRADO
        )
    db.commit()
    estado = "cerrado" if periodo.estado == EstadoPeriodo.CERRADO else "reabierto"
    return redirigir(
        f"/contabilidad/periodos?anio={anio}", request,
        f"Período {mes:02d}/{anio} {estado}.",
    )


@router.post("/cierre-ejercicio")
def cierre(request: Request, anio: int = Form(...), db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    usuario = usuario_actual(request, db)
    cuenta = cuenta_parametro(db, empresa.id, "cta_resultado")
    if cuenta is None:
        return redirigir("/contabilidad/periodos", request,
                         "Configura la cuenta «Resultado del ejercicio».", "error")
    try:
        comp = cerrar_ejercicio(db, empresa.id, anio, cuenta.id,
                                usuario.username if usuario else None)
    except ErrorContable as exc:
        return redirigir(f"/contabilidad/periodos?anio={anio}", request, str(exc), "error")
    return redirigir(
        f"/contabilidad/comprobantes/{comp.id}", request,
        f"Ejercicio {anio} cerrado con el comprobante {comp.folio}.",
    )


# ---------------------------------------------------------------------------
# Conciliación bancaria
# ---------------------------------------------------------------------------


@router.get("/conciliacion")
def conciliacion(request: Request, db: Session = Depends(get_db), cuenta_id: int = 0):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    desde, hasta = rango_mes(anio, mes)

    bancos = db.scalars(
        select(Cuenta)
        .where(Cuenta.empresa_id == empresa.id, Cuenta.es_banco.is_(True))
        .order_by(Cuenta.codigo)
    ).all()
    cuenta = db.get(Cuenta, cuenta_id) if cuenta_id else (bancos[0] if bancos else None)

    movimientos, saldo_libro, saldo_conciliado = [], 0.0, 0.0
    if cuenta is not None:
        saldo_libro, filas = libro_mayor(db, empresa.id, cuenta.id, desde, hasta)
        movimientos = [m for m, _ in filas]
        saldo_conciliado = saldo_libro + sum(
            pesos(m.debe) - pesos(m.haber) for m in movimientos if m.conciliado
        )
        saldo_libro = filas[-1][1] if filas else saldo_libro

    return render(request, "contabilidad/conciliacion.html", {
        "bancos": bancos, "cuenta": cuenta, "movimientos": movimientos,
        "saldo_libro": saldo_libro, "saldo_conciliado": saldo_conciliado,
    })


@router.post("/conciliacion/marcar")
async def marcar_conciliacion(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    form = await request.form()
    cuenta_id = entero(form.get("cuenta_id"))
    marcados = {entero(v) for v in form.getlist("conciliado")}

    movimientos = db.scalars(
        select(Movimiento).where(
            Movimiento.empresa_id == empresa.id,
            Movimiento.id.in_({entero(v) for v in form.getlist("movimiento_id")} or {0}),
        )
    ).all()
    for mov in movimientos:
        mov.conciliado = mov.id in marcados
        mov.fecha_conciliacion = date.today() if mov.conciliado else None
    db.commit()
    return redirigir(f"/contabilidad/conciliacion?cuenta_id={cuenta_id}", request,
                     f"{len(marcados)} movimiento(s) conciliado(s).")


# ---------------------------------------------------------------------------
# Exportación compartida
# ---------------------------------------------------------------------------


def _exportar(formato: str, titulo: str, encabezados: list[str], filas: list[list],
              empresa, subtitulo: str, columnas_monto: set[int], apaisado: bool = False):
    from contaflow.services.utils import slug

    nombre = f"{slug(titulo)}-{slug(subtitulo)}"
    if formato == "csv":
        return descarga(a_csv(encabezados, filas), f"{nombre}.csv", MIME["csv"])
    if formato == "xlsx":
        return descarga(
            a_excel(titulo, encabezados, filas, subtitulo=f"{empresa.razon_social} · {subtitulo}",
                    columnas_monto=columnas_monto),
            f"{nombre}.xlsx", MIME["xlsx"],
        )
    filas_pdf = [
        [formato_moneda(v) if i in columnas_monto and isinstance(v, (int, float)) else v
         for i, v in enumerate(fila)]
        for fila in filas
    ]
    return descarga(
        a_pdf(titulo, encabezados, filas_pdf, subtitulo=subtitulo,
              empresa=f"{empresa.razon_social} · {empresa.rut}", apaisado=apaisado,
              alineacion_derecha=columnas_monto),
        f"{nombre}.pdf", MIME["pdf"],
    )
