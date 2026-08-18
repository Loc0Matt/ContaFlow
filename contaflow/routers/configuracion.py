"""Configuración: cuentas por defecto, usuarios, parámetros y respaldos."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.config import (
    DIR_DATOS, RETENCION_HONORARIOS, TABLA_IMPUESTO_UNICO_UTM, TASAS_AFC, TASA_SALUD_LEGAL,
    TASA_SIS_EMPLEADOR, TOPE_IMPONIBLE_AFC_UF, TOPE_IMPONIBLE_AFP_UF,
)
from contaflow.database import get_db
from contaflow.models import AFP, Cuenta, Parametro, Usuario
from contaflow.services.exportar import crear_respaldo, listar_respaldos, restaurar_respaldo
from contaflow.services.plan_cuentas import CUENTAS_DEFECTO
from contaflow.services.remuneraciones import ASIGNACION_FAMILIAR
from contaflow.services.seguridad import hash_password, validar_password, verificar_password
from contaflow.web import decimal, entero, exigir_empresa, redirigir, render, usuario_actual

router = APIRouter(prefix="/configuracion")


@router.get("/cuentas")
def cuentas_defecto(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    parametros = {
        p.clave: p for p in db.scalars(
            select(Parametro).where(Parametro.empresa_id == empresa.id)
        ).all()
    }
    cuentas = db.scalars(
        select(Cuenta)
        .where(Cuenta.empresa_id == empresa.id, Cuenta.imputable.is_(True))
        .order_by(Cuenta.codigo)
    ).all()
    return render(request, "configuracion/cuentas.html", {
        "claves": CUENTAS_DEFECTO, "parametros": parametros, "cuentas": cuentas,
    })


@router.post("/cuentas/guardar")
async def guardar_cuentas_defecto(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    form = await request.form()
    for clave, (_, descripcion) in CUENTAS_DEFECTO.items():
        valor = form.get(clave, "")
        parametro = db.scalar(
            select(Parametro).where(Parametro.empresa_id == empresa.id, Parametro.clave == clave)
        )
        if parametro is None:
            parametro = Parametro(empresa_id=empresa.id, clave=clave, descripcion=descripcion)
            db.add(parametro)
        parametro.valor = str(entero(valor)) if entero(valor) else ""
    db.commit()
    return redirigir("/configuracion/cuentas", request, "Cuentas por defecto actualizadas.")


@router.get("/parametros")
def parametros(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    valores = {
        p.clave: p.valor for p in db.scalars(
            select(Parametro).where(Parametro.empresa_id == empresa.id)
        ).all()
    }
    return render(request, "configuracion/parametros.html", {
        "valores": valores,
        "afps": db.scalars(select(AFP).order_by(AFP.nombre)).all(),
        "tabla_impuesto": TABLA_IMPUESTO_UNICO_UTM,
        "retenciones": sorted(RETENCION_HONORARIOS.items()),
        "asignacion": ASIGNACION_FAMILIAR,
        "previsional": {
            "Tope imponible AFP / Salud (UF)": TOPE_IMPONIBLE_AFP_UF,
            "Tope imponible Seguro de Cesantía (UF)": TOPE_IMPONIBLE_AFC_UF,
            "Cotización legal de salud": f"{TASA_SALUD_LEGAL * 100:.0f}%",
            "SIS de cargo del empleador": f"{TASA_SIS_EMPLEADOR * 100:.2f}%",
            "AFC indefinido (trabajador / empleador)":
                f"{TASAS_AFC['INDEFINIDO'][0] * 100:.1f}% / {TASAS_AFC['INDEFINIDO'][1] * 100:.1f}%",
            "AFC plazo fijo (empleador)": f"{TASAS_AFC['PLAZO_FIJO'][1] * 100:.1f}%",
        },
    })


@router.post("/parametros/guardar")
async def guardar_parametros(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    form = await request.form()
    for clave in ("tasa_mutual", "proporcionalidad_iva", "dia_pago_remuneraciones"):
        valor = form.get(clave)
        if valor is None:
            continue
        parametro = db.scalar(
            select(Parametro).where(Parametro.empresa_id == empresa.id, Parametro.clave == clave)
        )
        if parametro is None:
            parametro = Parametro(empresa_id=empresa.id, clave=clave)
            db.add(parametro)
        parametro.valor = str(valor).strip()

    for afp in db.scalars(select(AFP)).all():
        nuevo = form.get(f"afp_{afp.id}")
        if nuevo not in (None, ""):
            afp.tasa = decimal(nuevo, float(afp.tasa))
    db.commit()
    return redirigir("/configuracion/parametros", request, "Parámetros actualizados.")


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------


@router.get("/usuarios")
def usuarios(request: Request, db: Session = Depends(get_db)):
    return render(request, "configuracion/usuarios.html", {
        "lista": db.scalars(select(Usuario).order_by(Usuario.username)).all(),
    })


@router.post("/usuarios/guardar")
def guardar_usuario(
    request: Request, db: Session = Depends(get_db),
    usuario_id: str = Form(""), username: str = Form(...), nombre: str = Form(...),
    email: str = Form(""), password: str = Form(""), activo: str = Form("on"),
):
    username = username.strip().lower()
    usuario = db.get(Usuario, int(usuario_id)) if usuario_id else None
    existente = db.scalar(select(Usuario).where(Usuario.username == username))
    if existente and (usuario is None or existente.id != usuario.id):
        return redirigir("/configuracion/usuarios", request,
                         f"El usuario «{username}» ya existe.", "error")

    if usuario is None:
        if not password:
            return redirigir("/configuracion/usuarios", request,
                             "Indica una contraseña para el usuario nuevo.", "error")

    if password:
        error = validar_password(password)
        if error:
            return redirigir("/configuracion/usuarios", request, error, "error")

    if usuario is None:
        usuario = Usuario(username=username, nombre=nombre, password_hash=hash_password(password))
        db.add(usuario)

    usuario.username = username
    usuario.nombre = nombre.strip()
    usuario.email = email.strip() or None
    usuario.activo = activo == "on"
    if password:
        usuario.password_hash = hash_password(password)
    db.commit()
    return redirigir("/configuracion/usuarios", request, f"Usuario «{username}» guardado.")


@router.post("/cambiar-password")
def cambiar_password(
    request: Request, db: Session = Depends(get_db),
    password_actual: str = Form(...), password_nueva: str = Form(...),
):
    usuario = usuario_actual(request, db)
    if usuario is None:
        return redirigir("/login")
    if not verificar_password(password_actual, usuario.password_hash):
        return redirigir("/configuracion/respaldos", request, "La contraseña actual no coincide.", "error")
    error = validar_password(password_nueva)
    if error:
        return redirigir("/configuracion/respaldos", request, error, "error")
    usuario.password_hash = hash_password(password_nueva)
    usuario.debe_cambiar_password = False
    db.commit()
    return redirigir("/configuracion/respaldos", request, "Contraseña actualizada.")


# ---------------------------------------------------------------------------
# Respaldos
# ---------------------------------------------------------------------------


@router.get("/respaldos")
def respaldos(request: Request, db: Session = Depends(get_db)):
    from contaflow.config import APP_VERSION
    from contaflow.services.migraciones import VERSION_ACTUAL, version_guardada

    archivos = [
        {"nombre": p.name, "tamano": p.stat().st_size // 1024, "fecha": p.stat().st_mtime}
        for p in listar_respaldos()
    ]
    return render(request, "configuracion/respaldos.html", {
        "archivos": archivos, "carpeta": str(DIR_DATOS),
        "app_version": APP_VERSION,
        "version_esquema": version_guardada(db.connection()),
        "version_esquema_actual": VERSION_ACTUAL,
    })


@router.post("/respaldos/crear")
def crear(request: Request):
    ruta = crear_respaldo()
    return redirigir("/configuracion/respaldos", request, f"Respaldo creado: {ruta.name}")


@router.post("/respaldos/restaurar")
def restaurar(request: Request, nombre: str = Form(...)):
    from contaflow.config import DIR_BACKUPS

    ruta = DIR_BACKUPS / Path(nombre).name
    try:
        restaurar_respaldo(ruta)
    except FileNotFoundError:
        return redirigir("/configuracion/respaldos", request, "El respaldo no existe.", "error")
    return redirigir("/configuracion/respaldos", request,
                     "Respaldo restaurado. Cierra y vuelve a abrir ContaFlow para recargar los datos.",
                     "warn")
