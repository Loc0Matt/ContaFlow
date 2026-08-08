"""Autenticación, panel principal y cambio de empresa/período."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contaflow.database import get_db
from contaflow.models import (
    ClaseDocumento, Comprobante, Documento, Empresa, EstadoComprobante, Trabajador, Usuario,
)
from contaflow.services.contabilidad import estado_resultados, saldos
from contaflow.services.formularios import generar_f29
from contaflow.services.seguridad import verificar_password
from contaflow.services.utils import pesos, rango_mes
from contaflow.web import empresa_actual, entero, redirigir, render, usuario_actual

router = APIRouter()


@router.get("/login")
def formulario_login(request: Request):
    return render(request, "login.html")


@router.post("/login")
def procesar_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    usuario = db.scalar(select(Usuario).where(Usuario.username == username.strip().lower()))
    if usuario is None or not usuario.activo or not verificar_password(password, usuario.password_hash):
        return render(request, "login.html", {"error": "Usuario o contraseña incorrectos."})
    request.session["usuario_id"] = usuario.id
    return redirigir("/", request, f"Bienvenido, {usuario.nombre}.")


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return redirigir("/login")


@router.get("/")
def panel(request: Request, db: Session = Depends(get_db)):
    usuario = usuario_actual(request, db)
    if usuario is None:
        return redirigir("/login")

    empresa = empresa_actual(request, db)
    if empresa is None:
        return render(request, "sin_empresa.html")

    hoy = date.today()
    anio = int(request.session.get("anio", hoy.year))
    mes = int(request.session.get("mes", hoy.month))
    desde, hasta = rango_mes(anio, mes)
    inicio_anio = date(anio, 1, 1)

    def total_documentos(clase: ClaseDocumento) -> tuple[int, int]:
        fila = db.execute(
            select(func.count(Documento.id), func.coalesce(func.sum(Documento.total), 0)).where(
                Documento.empresa_id == empresa.id,
                Documento.clase == clase,
                Documento.periodo_anio == anio,
                Documento.periodo_mes == mes,
                Documento.anulado.is_(False),
            )
        ).one()
        return int(fila[0]), pesos(fila[1])

    ventas_cant, ventas_monto = total_documentos(ClaseDocumento.VENTA)
    compras_cant, compras_monto = total_documentos(ClaseDocumento.COMPRA)

    eerr = estado_resultados(db, empresa.id, inicio_anio, hasta)

    try:
        f29 = generar_f29(db, empresa, anio, mes)
        iva_texto = (
            f"A pagar {f29.total_a_pagar:,}".replace(",", ".") if f29.total_a_pagar
            else f"Remanente {f29.remanente_siguiente:,}".replace(",", ".")
        )
    except Exception:  # pragma: no cover - el panel nunca debe caerse
        f29, iva_texto = None, "—"

    saldos_banco = [
        s for s in saldos(db, empresa.id, desde=inicio_anio, hasta=hasta, inicio_ejercicio=inicio_anio)
        if s.cuenta.es_banco or s.cuenta.codigo.startswith("1.1.01")
    ]

    ultimos = db.scalars(
        select(Comprobante)
        .where(Comprobante.empresa_id == empresa.id, Comprobante.estado == EstadoComprobante.CONTABILIZADO)
        .order_by(Comprobante.fecha.desc(), Comprobante.id.desc())
        .limit(8)
    ).all()

    vencimientos = db.scalars(
        select(Documento)
        .where(
            Documento.empresa_id == empresa.id,
            Documento.anulado.is_(False),
            Documento.pagado.is_(False),
            Documento.fecha_vencimiento.is_not(None),
            Documento.fecha_vencimiento <= hoy + timedelta(days=30),
        )
        .order_by(Documento.fecha_vencimiento)
        .limit(10)
    ).all()

    trabajadores = db.scalar(
        select(func.count(Trabajador.id)).where(
            Trabajador.empresa_id == empresa.id, Trabajador.activo.is_(True)
        )
    ) or 0

    return render(request, "panel.html", {
        "ventas_cant": ventas_cant, "ventas_monto": ventas_monto,
        "compras_cant": compras_cant, "compras_monto": compras_monto,
        "eerr": eerr, "f29": f29, "iva_texto": iva_texto,
        "saldos_banco": saldos_banco, "ultimos": ultimos,
        "vencimientos": vencimientos, "trabajadores": trabajadores,
    })


@router.post("/seleccionar-empresa")
def seleccionar_empresa(request: Request, empresa_id: int = Form(...), db: Session = Depends(get_db)):
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        return redirigir("/", request, "Empresa no encontrada.", "error")
    request.session["empresa_id"] = empresa.id
    destino = request.headers.get("referer", "/")
    return redirigir(destino, request, f"Trabajando en {empresa.razon_social}.")


@router.post("/seleccionar-periodo")
def seleccionar_periodo(
    request: Request, anio: int = Form(...), mes: int = Form(...),
):
    request.session["anio"] = entero(anio, date.today().year)
    request.session["mes"] = max(1, min(12, entero(mes, date.today().month)))
    destino = request.headers.get("referer", "/")
    return redirigir(destino)
