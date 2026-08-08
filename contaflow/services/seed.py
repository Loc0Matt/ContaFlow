"""Datos iniciales: catálogos globales y plan de cuentas por empresa."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.config import AFP_DEFECTO
from contaflow.models import AFP, CentroCosto, Cuenta, Empresa, Parametro, TipoDTE, Usuario
from contaflow.models.base import RolUsuario
from contaflow.services.plan_cuentas import CUENTAS_DEFECTO, PLAN_CUENTAS, TIPOS_DTE
from contaflow.services.seguridad import hash_password


def sembrar_globales(db: Session) -> None:
    """Catálogos que no dependen de la empresa: tipos DTE, AFP y usuario admin."""
    existentes = {c for (c,) in db.execute(select(TipoDTE.codigo))}
    for codigo, nombre, venta, compra, afecto, signo, electronico in TIPOS_DTE:
        if codigo in existentes:
            continue
        db.add(TipoDTE(
            codigo=codigo, nombre=nombre, es_venta=venta, es_compra=compra,
            afecto_iva=afecto, signo=signo, electronico=electronico,
        ))

    nombres_afp = {n for (n,) in db.execute(select(AFP.nombre))}
    for nombre, tasa in AFP_DEFECTO:
        if nombre not in nombres_afp:
            db.add(AFP(nombre=nombre, tasa=tasa))

    if not db.scalar(select(Usuario).limit(1)):
        db.add(Usuario(
            username="admin",
            nombre="Administrador",
            password_hash=hash_password("admin"),
            rol=RolUsuario.ADMIN,
        ))
    db.commit()


def sembrar_empresa(db: Session, empresa: Empresa) -> None:
    """Crea el plan de cuentas, centro de costo y parámetros de una empresa nueva."""
    if db.scalar(select(Cuenta).where(Cuenta.empresa_id == empresa.id).limit(1)):
        return

    por_codigo: dict[str, Cuenta] = {}
    for codigo, nombre, tipo, imputable, flags in PLAN_CUENTAS:
        padre_codigo = codigo.rsplit(".", 1)[0] if "." in codigo else None
        cuenta = Cuenta(
            empresa_id=empresa.id,
            codigo=codigo,
            nombre=nombre,
            tipo=tipo,
            nivel=codigo.count(".") + 1,
            imputable=imputable,
            requiere_auxiliar="aux" in flags,
            requiere_centro_costo=False,  # sugerido por el plan, no obligatorio
            es_banco="banco" in flags,
            grupo=codigo.split(".")[0] + "." + (codigo.split(".")[1] if "." in codigo else ""),
            padre=por_codigo.get(padre_codigo) if padre_codigo else None,
        )
        db.add(cuenta)
        db.flush()
        por_codigo[codigo] = cuenta

    db.add(CentroCosto(empresa_id=empresa.id, codigo="GEN", nombre="General"))

    for clave, (codigo, descripcion) in CUENTAS_DEFECTO.items():
        cuenta = por_codigo.get(codigo)
        db.add(Parametro(
            empresa_id=empresa.id,
            clave=clave,
            valor=str(cuenta.id) if cuenta else "",
            descripcion=descripcion,
        ))

    for clave, valor, desc in [
        ("tasa_mutual", "0.93", "Tasa mutual de seguridad (%)"),
        ("proporcionalidad_iva", "100", "% de IVA de uso común con derecho a crédito"),
        ("dia_pago_remuneraciones", "5", "Día de pago de remuneraciones"),
    ]:
        db.add(Parametro(empresa_id=empresa.id, clave=clave, valor=valor, descripcion=desc))

    db.commit()


def cuenta_parametro(db: Session, empresa_id: int, clave: str) -> Cuenta | None:
    """Devuelve la cuenta configurada para un parámetro (o None si no existe)."""
    param = db.scalar(
        select(Parametro).where(Parametro.empresa_id == empresa_id, Parametro.clave == clave)
    )
    if not param or not param.valor:
        return None
    return db.get(Cuenta, int(param.valor))


def valor_parametro(db: Session, empresa_id: int, clave: str, defecto: str = "") -> str:
    param = db.scalar(
        select(Parametro).where(Parametro.empresa_id == empresa_id, Parametro.clave == clave)
    )
    return param.valor if param and param.valor else defecto
