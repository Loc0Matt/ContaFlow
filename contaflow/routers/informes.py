"""Estados financieros, análisis de cuentas y exportaciones."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.database import get_db
from contaflow.models import Cuenta
from contaflow.services.contabilidad import analisis_auxiliar, balance_general, estado_resultados
from contaflow.services.exportar import a_csv, a_excel, a_pdf
from contaflow.services.utils import formato_moneda, nombre_mes, pesos, rango_mes, slug
from contaflow.web import MIME, descarga, exigir_empresa, periodo_sesion, redirigir, render

router = APIRouter(prefix="/informes")


@router.get("/resultados")
def resultados(request: Request, db: Session = Depends(get_db), formato: str = "",
               desde_mes: int = 1, hasta_mes: int = 0):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    hasta_mes = hasta_mes or mes
    desde, _ = rango_mes(anio, max(1, min(12, desde_mes)))
    _, hasta = rango_mes(anio, max(1, min(12, hasta_mes)))
    eerr = estado_resultados(db, empresa.id, desde, hasta)
    subtitulo = f"{nombre_mes(desde_mes)} a {nombre_mes(hasta_mes)} de {anio}"

    if formato:
        filas: list[list] = []

        def bloque(titulo: str, detalle: list, total: float):
            filas.append([titulo.upper(), "", ""])
            for codigo, nombre, monto in detalle:
                filas.append([codigo, nombre, pesos(monto)])
            filas.append(["", f"Total {titulo}", pesos(total)])

        bloque("Ingresos de explotación", eerr["ingresos"], eerr["total_ingresos"])
        bloque("Costos de explotación", eerr["costos"], eerr["total_costos"])
        filas.append(["", "MARGEN BRUTO", pesos(eerr["margen_bruto"])])
        bloque("Gastos de administración y ventas", eerr["gastos_admin"], eerr["total_gastos_admin"])
        filas.append(["", "RESULTADO OPERACIONAL", pesos(eerr["resultado_operacional"])])
        bloque("Otros ingresos", eerr["otros_ingresos"], eerr["total_otros_ingresos"])
        bloque("Gastos fuera de explotación", eerr["no_operacionales"],
               eerr["total_no_operacionales"])
        filas.append(["", "RESULTADO ANTES DE IMPUESTO", pesos(eerr["antes_impuesto"])])
        bloque("Impuesto a la renta", eerr["impuesto"], eerr["total_impuesto"])
        filas.append(["", "RESULTADO DEL EJERCICIO", pesos(eerr["resultado_neto"])])

        return _exportar(formato, "Estado de Resultados", ["Código", "Concepto", "Monto"],
                         filas, empresa, subtitulo, {2})

    return render(request, "informes/resultados.html", {
        "eerr": eerr, "desde_mes": desde_mes, "hasta_mes": hasta_mes, "subtitulo": subtitulo,
    })


@router.get("/balance-general")
def balance(request: Request, db: Session = Depends(get_db), formato: str = "", hasta_mes: int = 0):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    hasta_mes = hasta_mes or mes
    desde = date(anio, 1, 1)
    _, hasta = rango_mes(anio, hasta_mes)
    bg = balance_general(db, empresa.id, desde, hasta)
    subtitulo = f"Al 30/{hasta_mes:02d}/{anio}".replace("30/02", "28/02")

    if formato:
        filas: list[list] = []
        for clave in ("activo_corriente", "activo_no_corriente", "pasivo_corriente",
                      "pasivo_no_corriente", "patrimonio"):
            grupo = bg[clave]
            filas.append([grupo.titulo.upper(), "", ""])
            for codigo, nombre, monto in grupo.filas:
                filas.append([codigo, nombre, pesos(monto)])
            filas.append(["", f"Total {grupo.titulo}", pesos(grupo.total)])
        filas.append(["", "TOTAL ACTIVOS", pesos(bg["total_activo"])])
        filas.append(["", "TOTAL PASIVOS Y PATRIMONIO", pesos(bg["total_pasivo_patrimonio"])])
        return _exportar(formato, "Estado de Situación Financiera",
                         ["Código", "Concepto", "Monto"], filas, empresa, subtitulo, {2})

    return render(request, "informes/balance_general.html", {
        "bg": bg, "hasta_mes": hasta_mes, "subtitulo": subtitulo,
    })


@router.get("/analisis")
def analisis(request: Request, db: Session = Depends(get_db), cuenta_id: int = 0, formato: str = ""):
    empresa = exigir_empresa(request, db)
    anio, mes = periodo_sesion(request)
    _, hasta = rango_mes(anio, mes)

    cuentas = db.scalars(
        select(Cuenta)
        .where(Cuenta.empresa_id == empresa.id, Cuenta.requiere_auxiliar.is_(True))
        .order_by(Cuenta.codigo)
    ).all()
    cuenta = db.get(Cuenta, cuenta_id) if cuenta_id else (cuentas[0] if cuentas else None)
    filas = []
    if cuenta is not None and cuenta.empresa_id == empresa.id:
        filas = analisis_auxiliar(db, empresa.id, cuenta.id, hasta)

    if formato and cuenta is not None:
        encabezados = ["RUT", "Razón social", "Debe", "Haber", "Saldo"]
        datos = [[r[0], r[1], pesos(r[2]), pesos(r[3]), pesos(r[4])] for r in filas]
        datos.append(["", "TOTAL", pesos(sum(r[2] for r in filas)),
                      pesos(sum(r[3] for r in filas)), pesos(sum(r[4] for r in filas))])
        return _exportar(formato, f"Análisis de cuenta {cuenta.codigo}", encabezados, datos,
                         empresa, f"{cuenta.nombre} · al {mes:02d}/{anio}", {2, 3, 4})

    return render(request, "informes/analisis.html", {
        "cuentas": cuentas, "cuenta": cuenta, "filas": filas,
        "total": sum(r[4] for r in filas),
    })


def _exportar(formato: str, titulo: str, encabezados: list[str], filas: list[list],
              empresa, subtitulo: str, columnas_monto: set[int]):
    nombre = f"{slug(titulo)}-{slug(subtitulo)}"
    if formato == "csv":
        return descarga(a_csv(encabezados, filas), f"{nombre}.csv", MIME["csv"])
    if formato == "xlsx":
        return descarga(
            a_excel(titulo, encabezados, filas,
                    subtitulo=f"{empresa.razon_social} · {subtitulo}",
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
              empresa=f"{empresa.razon_social} · {empresa.rut}",
              alineacion_derecha=columnas_monto),
        f"{nombre}.pdf", MIME["pdf"],
    )
