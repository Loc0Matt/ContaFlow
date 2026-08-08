"""Construcción de la aplicación FastAPI."""
from __future__ import annotations

import logging
from html import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from contaflow.config import APP_TITULO, APP_VERSION, DIR_STATIC, SESSION_SECRET
from contaflow.database import SessionLocal, crear_esquema
from contaflow.routers import (
    activofijo, configuracion, contabilidad, empresas, general, informes, maestros, remuneraciones,
    tributario,
)
from contaflow.services.contabilidad import ErrorContable
from contaflow.services.seed import sembrar_globales
from contaflow.web import SinEmpresa, render

log = logging.getLogger("contaflow")

#: Rutas accesibles sin sesión iniciada.
RUTAS_PUBLICAS = {"/login", "/logout", "/salud", "/firma", "/logo"}


def crear_app() -> FastAPI:
    crear_esquema()
    with SessionLocal() as db:
        sembrar_globales(db)

    app = FastAPI(title=APP_TITULO, version=APP_VERSION, docs_url=None, redoc_url=None)

    if DIR_STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(DIR_STATIC)), name="static")

    @app.middleware("http")
    async def exigir_sesion(request: Request, call_next):
        ruta = request.url.path
        if ruta.startswith("/static") or ruta in RUTAS_PUBLICAS:
            return await call_next(request)
        if not request.session.get("usuario_id"):
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)

    # Starlette ejecuta primero el último middleware agregado: la sesión debe
    # registrarse después de `exigir_sesion` para quedar por fuera de él.
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 12)

    @app.exception_handler(SinEmpresa)
    async def sin_empresa(request: Request, _exc: SinEmpresa):
        return render(request, "sin_empresa.html")

    @app.exception_handler(ErrorContable)
    async def error_contable(request: Request, exc: ErrorContable):
        return render(request, "error.html", {"mensaje_error": str(exc)}, status_code=400)

    @app.exception_handler(500)
    async def error_interno(request: Request, exc: Exception):  # pragma: no cover
        # Este manejador corre fuera del SessionMiddleware, así que no puede
        # renderizar el layout completo (necesita request.session).
        log.exception("Error no controlado en %s", request.url.path)
        return HTMLResponse(
            f"<h1>Ocurrió un problema</h1><pre>{escape(str(exc))}</pre>"
            '<p><a href="/">Volver al panel</a></p>',
            status_code=500,
        )

    @app.get("/salud", include_in_schema=False)
    def salud():
        return {"estado": "ok", "version": APP_VERSION}

    @app.get("/logo", include_in_schema=False)
    def logo():
        """Sirve el logotipo, recortado y cacheado en la carpeta de datos."""
        from fastapi.responses import FileResponse

        from contaflow.marca import archivo_a_servir

        archivo = archivo_a_servir()
        if archivo is None:
            return Response(status_code=404)
        ruta, tipo = archivo
        return FileResponse(ruta, media_type=tipo,
                            headers={"Cache-Control": "max-age=3600"})

    @app.get("/firma", include_in_schema=False)
    def firma():
        """Sello de autoría. No figura en el menú; se consulta por URL directa."""
        from contaflow.firma import HUELLA, intacto, linea_credito, sello

        return {
            **sello(),
            "huella": HUELLA,
            "intacto": intacto(),
            "credito": linea_credito(),
        }

    for modulo in (general, empresas, contabilidad, tributario, maestros, remuneraciones,
                   activofijo, informes, configuracion):
        app.include_router(modulo.router)

    return app


app = crear_app()
