"""Aplicación FastAPI: middleware de sesión, contexto de plantillas y utilidades."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.config import APP_NAME, APP_TITULO, APP_VERSION, DIR_TEMPLATES
from contaflow.models import Empresa, Usuario
from contaflow.services.utils import (
    formatear_rut, formato_decimal, formato_fecha, formato_moneda, nombre_mes, periodo_etiqueta,
)

templates = Jinja2Templates(directory=str(DIR_TEMPLATES))
templates.env.filters["moneda"] = formato_moneda
templates.env.filters["decimal"] = formato_decimal
templates.env.filters["rut"] = formatear_rut
templates.env.filters["fecha"] = formato_fecha
templates.env.globals.update(
    APP_NAME=APP_NAME, APP_TITULO=APP_TITULO, APP_VERSION=APP_VERSION,
    nombre_mes=nombre_mes, periodo_etiqueta=periodo_etiqueta, hoy=date.today,
    MESES=[(i, nombre_mes(i)) for i in range(1, 13)],
)


class SinEmpresa(Exception):
    """No hay empresa seleccionada en la sesión."""


def usuario_actual(request: Request, db: Session) -> Usuario | None:
    uid = request.session.get("usuario_id")
    return db.get(Usuario, uid) if uid else None


def empresa_actual(request: Request, db: Session) -> Empresa | None:
    eid = request.session.get("empresa_id")
    empresa = db.get(Empresa, eid) if eid else None
    if empresa is None:
        empresa = db.scalar(select(Empresa).where(Empresa.activa.is_(True)).order_by(Empresa.id))
        if empresa:
            request.session["empresa_id"] = empresa.id
    return empresa


def exigir_empresa(request: Request, db: Session) -> Empresa:
    empresa = empresa_actual(request, db)
    if empresa is None:
        raise SinEmpresa()
    return empresa


def periodo_sesion(request: Request) -> tuple[int, int]:
    """Año y mes de trabajo activos (se recuerdan entre pantallas)."""
    hoy = date.today()
    return (
        int(request.session.get("anio", hoy.year)),
        int(request.session.get("mes", hoy.month)),
    )


def render(
    request: Request,
    plantilla: str,
    contexto: dict[str, Any] | None = None,
    *,
    status_code: int = 200,
    **extra,
) -> Response:
    """Renderiza una plantilla añadiendo el contexto común de la aplicación."""
    from contaflow.database import SessionLocal

    datos: dict[str, Any] = {}
    db = SessionLocal()
    try:
        anio, mes = periodo_sesion(request)
        datos.update(
            usuario=usuario_actual(request, db),
            empresa=empresa_actual(request, db),
            empresas=db.scalars(
                select(Empresa).where(Empresa.activa.is_(True)).order_by(Empresa.razon_social)
            ).all(),
            anio_activo=anio,
            mes_activo=mes,
            mensajes=consumir_mensajes(request),
        )
    finally:
        db.close()
    datos.update(contexto or {})
    datos.update(extra)
    return templates.TemplateResponse(request, plantilla, datos, status_code=status_code)


def mensaje(request: Request, texto: str, tipo: str = "ok") -> None:
    """Guarda un mensaje flash para mostrarlo tras una redirección."""
    cola = request.session.setdefault("mensajes", [])
    cola.append({"texto": texto, "tipo": tipo})
    request.session["mensajes"] = cola[-5:]


def consumir_mensajes(request: Request) -> list[dict]:
    cola = request.session.get("mensajes", [])
    request.session["mensajes"] = []
    return cola


def redirigir(url: str, request: Request | None = None, texto: str = "", tipo: str = "ok"):
    if request is not None and texto:
        mensaje(request, texto, tipo)
    return RedirectResponse(url, status_code=303)


def descarga(contenido: bytes, nombre: str, tipo_mime: str) -> Response:
    return Response(
        content=contenido,
        media_type=tipo_mime,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


MIME = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def entero(valor: Any, defecto: int = 0) -> int:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return defecto


def decimal(valor: Any, defecto: float = 0.0) -> float:
    from contaflow.services.utils import a_decimal

    if valor in (None, ""):
        return defecto
    return float(a_decimal(valor))
