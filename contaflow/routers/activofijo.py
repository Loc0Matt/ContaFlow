"""Registro de activo fijo, depreciación mensual y bajas."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.database import get_db
from contaflow.models import ActivoFijo, CentroCosto, Cuenta
from contaflow.services.activofijo import (
    VIDAS_UTILES_SII, calendario_depreciacion, dar_de_baja, procesar_depreciacion_mensual,
    resumen_activo_fijo,
)
from contaflow.services.contabilidad import ErrorContable
from contaflow.services.exportar import a_csv, a_excel, a_pdf
from contaflow.services.utils import (
    formato_fecha, formato_moneda, parse_fecha, periodo_etiqueta, pesos,
)
from contaflow.web import (
    MIME, decimal, descarga, entero, exigir_empresa, periodo_sesion, redirigir, render,
    usuario_actual,
)

router = APIRouter(prefix="/activo-fijo")


@router.get("")
def lista(request: Request, db: Session = Depends(get_db), formato: str = ""):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    filas = resumen_activo_fijo(db, empresa.id, anio, mes)

    if formato:
        encabezados = ["Código", "Nombre", "Categoría", "F. Adquisición", "Costo",
                       "Vida útil (meses)", "Depreciación mes", "Dep. acumulada", "Valor libro"]
        datos = [[
            f["activo"].codigo, f["activo"].nombre, f["activo"].categoria or "",
            formato_fecha(f["activo"].fecha_adquisicion), f["costo"], f["vida_util"],
            f["depreciacion_mes"], f["depreciacion_acumulada"], f["valor_libro"],
        ] for f in filas]
        montos = {4, 6, 7, 8}
        nombre = f"activo-fijo-{anio}{mes:02d}"
        if formato == "csv":
            return descarga(a_csv(encabezados, datos), f"{nombre}.csv", MIME["csv"])
        if formato == "pdf":
            datos_pdf = [
                [formato_moneda(v) if i in montos and isinstance(v, int) else v
                 for i, v in enumerate(d)] for d in datos
            ]
            return descarga(
                a_pdf("Libro de Activo Fijo", encabezados, datos_pdf,
                      subtitulo=f"Al {periodo_etiqueta(anio, mes)}",
                      empresa=f"{empresa.razon_social} · {empresa.rut}",
                      apaisado=True, alineacion_derecha=montos),
                f"{nombre}.pdf", MIME["pdf"],
            )
        return descarga(
            a_excel("Activo Fijo", encabezados, datos,
                    subtitulo=f"{empresa.razon_social} · Al {periodo_etiqueta(anio, mes)}",
                    columnas_monto=montos),
            f"{nombre}.xlsx", MIME["xlsx"],
        )

    cuentas = db.scalars(
        select(Cuenta)
        .where(Cuenta.empresa_id == empresa.id, Cuenta.imputable.is_(True))
        .order_by(Cuenta.codigo)
    ).all()
    return render(request, "activofijo/lista.html", {
        "filas": filas, "cuentas": cuentas, "vidas_utiles": VIDAS_UTILES_SII,
        "centros": db.scalars(
            select(CentroCosto).where(CentroCosto.empresa_id == empresa.id)
        ).all(),
        "totales": {
            "costo": sum(f["costo"] for f in filas),
            "mes": sum(f["depreciacion_mes"] for f in filas),
            "acumulada": sum(f["depreciacion_acumulada"] for f in filas),
            "libro": sum(f["valor_libro"] for f in filas),
        },
    })


@router.post("/guardar")
async def guardar(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    form = await request.form()
    activo_id = entero(form.get("activo_id"))
    activo = db.get(ActivoFijo, activo_id) if activo_id else None
    codigo = (form.get("codigo") or "").strip()

    existente = db.scalar(
        select(ActivoFijo).where(ActivoFijo.empresa_id == empresa.id, ActivoFijo.codigo == codigo)
    )
    if existente and (activo is None or existente.id != activo.id):
        return redirigir("/activo-fijo", request, f"Ya existe el activo {codigo}.", "error")

    if activo is None:
        activo = ActivoFijo(empresa_id=empresa.id, codigo=codigo,
                            fecha_adquisicion=date.today())
        db.add(activo)

    activo.codigo = codigo
    activo.nombre = (form.get("nombre") or "").strip()
    activo.categoria = (form.get("categoria") or "").strip() or None
    activo.fecha_adquisicion = parse_fecha(form.get("fecha_adquisicion"), date.today())
    activo.valor_adquisicion = pesos(decimal(form.get("valor_adquisicion")))
    activo.valor_residual = pesos(decimal(form.get("valor_residual")))
    activo.vida_util_meses = max(1, entero(form.get("vida_util_meses"), 36))
    activo.usa_acelerada = form.get("usa_acelerada") == "on"
    activo.cuenta_activo_id = entero(form.get("cuenta_activo_id")) or None
    activo.cuenta_depreciacion_id = entero(form.get("cuenta_depreciacion_id")) or None
    activo.cuenta_gasto_id = entero(form.get("cuenta_gasto_id")) or None
    activo.centro_costo_id = entero(form.get("centro_costo_id")) or None
    activo.observacion = (form.get("observacion") or "").strip() or None
    db.commit()
    return redirigir("/activo-fijo", request, f"Activo {activo.codigo} guardado.")


@router.get("/{activo_id}/calendario")
def calendario(activo_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    activo = db.get(ActivoFijo, activo_id)
    if activo is None or activo.empresa_id != empresa.id:
        return redirigir("/activo-fijo", request, "Activo no encontrado.", "error")
    return render(request, "activofijo/calendario.html", {
        "activo": activo, "filas": calendario_depreciacion(activo),
    })


@router.post("/depreciar")
def depreciar(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    usuario = usuario_actual(request, db)
    anio, mes = periodo_sesion(request)
    try:
        comprobante, registros = procesar_depreciacion_mensual(
            db, empresa.id, anio, mes, usuario.username if usuario else None
        )
    except ErrorContable as exc:
        return redirigir("/activo-fijo", request, str(exc), "error")
    if comprobante is None:
        return redirigir("/activo-fijo", request,
                         f"No hay depreciación que registrar en {periodo_etiqueta(anio, mes)}.", "warn")
    return redirigir(f"/contabilidad/comprobantes/{comprobante.id}", request,
                     f"Depreciación de {len(registros)} activo(s) contabilizada "
                     f"en {comprobante.folio}.")


@router.post("/{activo_id}/baja")
def baja(activo_id: int, request: Request, db: Session = Depends(get_db),
         fecha: str = Form(""), valor_venta: str = Form("0")):
    empresa = exigir_empresa(request, db)
    usuario = usuario_actual(request, db)
    activo = db.get(ActivoFijo, activo_id)
    if activo is None or activo.empresa_id != empresa.id:
        return redirigir("/activo-fijo", request, "Activo no encontrado.", "error")
    try:
        comp = dar_de_baja(db, activo, parse_fecha(fecha, date.today()),
                           decimal(valor_venta), usuario=usuario.username if usuario else None)
    except ErrorContable as exc:
        return redirigir("/activo-fijo", request, str(exc), "error")
    return redirigir(f"/contabilidad/comprobantes/{comp.id}", request,
                     f"Activo {activo.codigo} dado de baja en {comp.folio}.")
