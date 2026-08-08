"""Gestión de empresas (alta, edición y desactivación)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.database import get_db
from contaflow.models import Empresa, RegimenTributario
from contaflow.services.seed import sembrar_empresa
from contaflow.services.utils import normalizar_rut, parse_fecha, rut_valido
from contaflow.web import decimal, redirigir, render

router = APIRouter(prefix="/empresas")


@router.get("")
def listar(request: Request, db: Session = Depends(get_db)):
    empresas = db.scalars(select(Empresa).order_by(Empresa.razon_social)).all()
    return render(request, "empresas/lista.html", {"lista": empresas})


@router.get("/nueva")
def nueva(request: Request):
    return render(request, "empresas/form.html", {
        "registro": None, "regimenes": list(RegimenTributario),
    })


@router.get("/{empresa_id}/editar")
def editar(empresa_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        return redirigir("/empresas", request, "Empresa no encontrada.", "error")
    return render(request, "empresas/form.html", {
        "registro": empresa, "regimenes": list(RegimenTributario),
    })


@router.post("/guardar")
def guardar(
    request: Request,
    db: Session = Depends(get_db),
    empresa_id: str = Form(""),
    rut: str = Form(...),
    razon_social: str = Form(...),
    nombre_fantasia: str = Form(""),
    giro: str = Form(""),
    actividad_codigo: str = Form(""),
    direccion: str = Form(""),
    comuna: str = Form(""),
    ciudad: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    regimen: str = Form(RegimenTributario.ART14D3.value),
    representante_rut: str = Form(""),
    representante_nombre: str = Form(""),
    fecha_inicio_actividades: str = Form(""),
    tasa_ppm: str = Form("0.25"),
    contabilidad_completa: str = Form("on"),
):
    if not rut_valido(rut):
        return redirigir("/empresas/nueva", request, f"El RUT {rut} no es válido.", "error")

    rut_norm = normalizar_rut(rut)
    empresa = db.get(Empresa, int(empresa_id)) if empresa_id else None
    duplicada = db.scalar(select(Empresa).where(Empresa.rut == rut_norm))
    if duplicada and (empresa is None or duplicada.id != empresa.id):
        return redirigir("/empresas", request, f"Ya existe una empresa con RUT {rut_norm}.", "error")

    nueva_empresa = empresa is None
    if nueva_empresa:
        empresa = Empresa(rut=rut_norm)
        db.add(empresa)

    empresa.rut = rut_norm
    empresa.razon_social = razon_social.strip()
    empresa.nombre_fantasia = nombre_fantasia.strip() or None
    empresa.giro = giro.strip() or None
    empresa.actividad_codigo = actividad_codigo.strip() or None
    empresa.direccion = direccion.strip() or None
    empresa.comuna = comuna.strip() or None
    empresa.ciudad = ciudad.strip() or None
    empresa.telefono = telefono.strip() or None
    empresa.email = email.strip() or None
    empresa.regimen = RegimenTributario(regimen)
    empresa.representante_rut = normalizar_rut(representante_rut) or None
    empresa.representante_nombre = representante_nombre.strip() or None
    empresa.fecha_inicio_actividades = parse_fecha(fecha_inicio_actividades)
    empresa.tasa_ppm = decimal(tasa_ppm, 0.25)
    empresa.contabilidad_completa = contabilidad_completa == "on"
    db.commit()

    if nueva_empresa:
        sembrar_empresa(db, empresa)
        request.session["empresa_id"] = empresa.id
        return redirigir(
            "/empresas", request,
            f"Empresa creada con su plan de cuentas chileno ({empresa.razon_social}).",
        )
    return redirigir("/empresas", request, "Empresa actualizada.")


@router.post("/{empresa_id}/estado")
def cambiar_estado(empresa_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        return redirigir("/empresas", request, "Empresa no encontrada.", "error")
    empresa.activa = not empresa.activa
    db.commit()
    estado = "activada" if empresa.activa else "desactivada"
    return redirigir("/empresas", request, f"Empresa {estado}.")
