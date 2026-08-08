"""Maestros: plan de cuentas, entidades, centros de costo e indicadores."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.models import CentroCosto, Cuenta, Entidad, Indicador, TipoCuenta
from contaflow.database import get_db
from contaflow.services.exportar import a_csv, a_excel
from contaflow.services.utils import normalizar_rut, pesos, rut_valido
from contaflow.web import (
    MIME, decimal, descarga, entero, exigir_empresa, periodo_sesion, redirigir, render,
)

router = APIRouter(prefix="/maestros")


# ---------------------------------------------------------------------------
# Plan de cuentas
# ---------------------------------------------------------------------------


@router.get("/cuentas")
def cuentas(request: Request, db: Session = Depends(get_db), texto: str = "", formato: str = ""):
    empresa = exigir_empresa(request, db)
    consulta = select(Cuenta).where(Cuenta.empresa_id == empresa.id).order_by(Cuenta.codigo)
    if texto:
        consulta = consulta.where(
            Cuenta.nombre.ilike(f"%{texto}%") | Cuenta.codigo.ilike(f"{texto}%")
        )
    lista = db.scalars(consulta).all()

    if formato:
        encabezados = ["Código", "Nombre", "Tipo", "Imputable", "Auxiliar", "Banco"]
        filas = [
            [c.codigo, c.nombre, c.tipo.value, "Sí" if c.imputable else "No",
             "Sí" if c.requiere_auxiliar else "No", "Sí" if c.es_banco else "No"]
            for c in lista
        ]
        if formato == "csv":
            return descarga(a_csv(encabezados, filas), "plan-de-cuentas.csv", MIME["csv"])
        return descarga(
            a_excel("Plan de Cuentas", encabezados, filas, subtitulo=empresa.razon_social),
            "plan-de-cuentas.xlsx", MIME["xlsx"],
        )

    return render(request, "maestros/cuentas.html", {
        "lista": lista, "texto": texto, "tipos": list(TipoCuenta),
    })


@router.post("/cuentas/guardar")
def guardar_cuenta(
    request: Request, db: Session = Depends(get_db),
    cuenta_id: str = Form(""), codigo: str = Form(...), nombre: str = Form(...),
    tipo: str = Form(...), imputable: str = Form(""), requiere_auxiliar: str = Form(""),
    requiere_centro_costo: str = Form(""), es_banco: str = Form(""),
):
    empresa = exigir_empresa(request, db)
    codigo = codigo.strip()
    cuenta = db.get(Cuenta, int(cuenta_id)) if cuenta_id else None
    existente = db.scalar(
        select(Cuenta).where(Cuenta.empresa_id == empresa.id, Cuenta.codigo == codigo)
    )
    if existente and (cuenta is None or existente.id != cuenta.id):
        return redirigir("/maestros/cuentas", request, f"Ya existe la cuenta {codigo}.", "error")

    if cuenta is None:
        cuenta = Cuenta(empresa_id=empresa.id, codigo=codigo)
        db.add(cuenta)

    padre_codigo = codigo.rsplit(".", 1)[0] if "." in codigo else None
    padre = db.scalar(
        select(Cuenta).where(Cuenta.empresa_id == empresa.id, Cuenta.codigo == padre_codigo)
    ) if padre_codigo else None

    cuenta.codigo = codigo
    cuenta.nombre = nombre.strip()
    cuenta.tipo = TipoCuenta(tipo)
    cuenta.nivel = codigo.count(".") + 1
    cuenta.padre_id = padre.id if padre else None
    cuenta.imputable = imputable == "on"
    cuenta.requiere_auxiliar = requiere_auxiliar == "on"
    cuenta.requiere_centro_costo = requiere_centro_costo == "on"
    cuenta.es_banco = es_banco == "on"
    db.commit()
    return redirigir("/maestros/cuentas", request, f"Cuenta {codigo} guardada.")


@router.post("/cuentas/{cuenta_id}/estado")
def estado_cuenta(cuenta_id: int, request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    cuenta = db.get(Cuenta, cuenta_id)
    if cuenta is None or cuenta.empresa_id != empresa.id:
        return redirigir("/maestros/cuentas", request, "Cuenta no encontrada.", "error")
    cuenta.activa = not cuenta.activa
    db.commit()
    return redirigir("/maestros/cuentas", request,
                     f"Cuenta {cuenta.codigo} {'activada' if cuenta.activa else 'desactivada'}.")


# ---------------------------------------------------------------------------
# Clientes y proveedores
# ---------------------------------------------------------------------------


@router.get("/entidades")
def entidades(request: Request, db: Session = Depends(get_db), texto: str = "", filtro: str = ""):
    empresa = exigir_empresa(request, db)
    consulta = select(Entidad).where(Entidad.empresa_id == empresa.id).order_by(Entidad.razon_social)
    if texto:
        consulta = consulta.where(
            Entidad.razon_social.ilike(f"%{texto}%") | Entidad.rut.ilike(f"%{texto}%")
        )
    if filtro == "clientes":
        consulta = consulta.where(Entidad.es_cliente.is_(True))
    elif filtro == "proveedores":
        consulta = consulta.where(Entidad.es_proveedor.is_(True))
    return render(request, "maestros/entidades.html", {
        "lista": db.scalars(consulta).all(), "texto": texto, "filtro": filtro,
    })


@router.post("/entidades/guardar")
def guardar_entidad(
    request: Request, db: Session = Depends(get_db),
    entidad_id: str = Form(""), rut: str = Form(...), razon_social: str = Form(...),
    giro: str = Form(""), direccion: str = Form(""), comuna: str = Form(""),
    email: str = Form(""), telefono: str = Form(""),
    es_cliente: str = Form(""), es_proveedor: str = Form(""),
):
    empresa = exigir_empresa(request, db)
    if not rut_valido(rut):
        return redirigir("/maestros/entidades", request, f"El RUT «{rut}» no es válido.", "error")
    rut_norm = normalizar_rut(rut)

    entidad = db.get(Entidad, int(entidad_id)) if entidad_id else None
    existente = db.scalar(
        select(Entidad).where(Entidad.empresa_id == empresa.id, Entidad.rut == rut_norm)
    )
    if existente and (entidad is None or existente.id != entidad.id):
        return redirigir("/maestros/entidades", request,
                         f"Ya existe un registro con RUT {rut_norm}.", "error")
    if entidad is None:
        entidad = Entidad(empresa_id=empresa.id, rut=rut_norm)
        db.add(entidad)

    entidad.rut = rut_norm
    entidad.razon_social = razon_social.strip()
    entidad.giro = giro.strip() or None
    entidad.direccion = direccion.strip() or None
    entidad.comuna = comuna.strip() or None
    entidad.email = email.strip() or None
    entidad.telefono = telefono.strip() or None
    entidad.es_cliente = es_cliente == "on"
    entidad.es_proveedor = es_proveedor == "on"
    db.commit()
    return redirigir("/maestros/entidades", request, f"{entidad.razon_social} guardado.")


# ---------------------------------------------------------------------------
# Centros de costo
# ---------------------------------------------------------------------------


@router.get("/centros-costo")
def centros(request: Request, db: Session = Depends(get_db)):
    empresa = exigir_empresa(request, db)
    lista = db.scalars(
        select(CentroCosto).where(CentroCosto.empresa_id == empresa.id).order_by(CentroCosto.codigo)
    ).all()
    return render(request, "maestros/centros_costo.html", {"lista": lista})


@router.post("/centros-costo/guardar")
def guardar_centro(
    request: Request, db: Session = Depends(get_db),
    centro_id: str = Form(""), codigo: str = Form(...), nombre: str = Form(...),
):
    empresa = exigir_empresa(request, db)
    centro = db.get(CentroCosto, int(centro_id)) if centro_id else None
    if centro is None:
        centro = CentroCosto(empresa_id=empresa.id)
        db.add(centro)
    centro.codigo = codigo.strip().upper()
    centro.nombre = nombre.strip()
    db.commit()
    return redirigir("/maestros/centros-costo", request, "Centro de costo guardado.")


# ---------------------------------------------------------------------------
# Indicadores económicos
# ---------------------------------------------------------------------------


@router.get("/indicadores")
def indicadores(request: Request, db: Session = Depends(get_db), anio: int = 0):
    anio_activo, _ = periodo_sesion(request)
    anio = anio or anio_activo
    registros = {
        i.mes: i for i in db.scalars(select(Indicador).where(Indicador.anio == anio)).all()
    }
    return render(request, "maestros/indicadores.html", {"anio": anio, "registros": registros})


@router.post("/indicadores/guardar")
async def guardar_indicadores(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    anio = entero(form.get("anio"), 0)
    if not anio:
        return redirigir("/maestros/indicadores", request, "Año inválido.", "error")

    for mes in range(1, 13):
        uf = decimal(form.get(f"uf_{mes}"))
        utm = decimal(form.get(f"utm_{mes}"))
        if not uf and not utm:
            continue
        registro = db.scalar(
            select(Indicador).where(Indicador.anio == anio, Indicador.mes == mes)
        )
        if registro is None:
            registro = Indicador(anio=anio, mes=mes)
            db.add(registro)
        registro.uf = uf
        registro.utm = utm
        registro.uta = decimal(form.get(f"uta_{mes}")) or utm * 12
        registro.ipc = decimal(form.get(f"ipc_{mes}"))
        registro.ingreso_minimo = decimal(form.get(f"imm_{mes}"))
        registro.dolar = decimal(form.get(f"dolar_{mes}"))
    db.commit()
    return redirigir(f"/maestros/indicadores?anio={anio}", request,
                     f"Indicadores de {anio} actualizados.")


@router.post("/indicadores/copiar")
def copiar_indicadores(
    request: Request, db: Session = Depends(get_db),
    anio_origen: int = Form(...), anio_destino: int = Form(...),
):
    """Duplica el año anterior como punto de partida (luego se ajusta a mano)."""
    origen = db.scalars(select(Indicador).where(Indicador.anio == anio_origen)).all()
    if not origen:
        return redirigir("/maestros/indicadores", request,
                         f"No hay indicadores cargados en {anio_origen}.", "error")
    for ind in origen:
        destino = db.scalar(
            select(Indicador).where(Indicador.anio == anio_destino, Indicador.mes == ind.mes)
        )
        if destino is None:
            destino = Indicador(anio=anio_destino, mes=ind.mes)
            db.add(destino)
        destino.uf, destino.utm, destino.uta = ind.uf, ind.utm, ind.uta
        destino.ipc, destino.ingreso_minimo, destino.dolar = ind.ipc, ind.ingreso_minimo, ind.dolar
    db.commit()
    return redirigir(f"/maestros/indicadores?anio={anio_destino}", request,
                     f"Indicadores copiados de {anio_origen} a {anio_destino}. Ajusta los valores.")
