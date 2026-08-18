"""Perfiles de instalación: qué tan cargada se ve la interfaz.

Se elige una sola vez, al abrir ContaFlow por primera vez — antes incluso de
crear la primera empresa — y aplica a toda la instalación, no a una empresa
en particular:

- **Emprendedor** / **Pyme**: alguien que administra SU PROPIO negocio, no
  una cartera de clientes. Se le permite crear una sola empresa (la suya), y
  el menú se simplifica según `SECCIONES` más abajo.
- **Contador**: alguien que administra varias empresas de clientes
  distintos. Sin tope de empresas, sin ninguna sección oculta — el
  comportamiento completo de ContaFlow, tal como era antes de este archivo.

Qué se oculta por perfil está definido acá, en el propio código — no se
configura desde la interfaz. Editable a mano: cambias True/False, recompilas,
y la siguiente versión del .exe sale con el menú ajustado.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.models import Parametro

CLAVE = "perfil_instalacion"

PERFILES = ("emprendedor", "pyme", "contador")

ETIQUETAS = {
    "emprendedor": "Emprendedor",
    "pyme": "Pyme",
    "contador": "Contador / cartera de clientes",
}

DESCRIPCIONES = {
    "emprendedor": "Administro mi propio negocio, yo solo — sin experiencia contable previa.",
    "pyme": "Administro mi propia empresa, con uno o más trabajadores.",
    "contador": "Llevo la contabilidad de varios clientes distintos.",
}

#: Cuántas empresas puede crear cada perfil. None = sin tope.
TOPE_EMPRESAS: dict[str, int | None] = {"emprendedor": 1, "pyme": 1, "contador": None}

#: clave = id interno de la sección (coincide con los bloques de
#: templates/base.html), valor = (emprendedor, pyme, contador). Cualquier
#: sección que NO aparezca acá se considera siempre visible, en los tres
#: perfiles — son el núcleo operativo o administración de la instalación,
#: no algo que dependa del perfil.
SECCIONES: dict[str, tuple[bool, bool, bool]] = {
    "formulario_22":         (False, True,  True),
    "comprobantes_manuales": (False, True,  True),
    "libro_diario":          (False, True,  True),
    "libro_mayor":           (False, True,  True),
    "balance_8_columnas":    (False, False, True),
    "conciliacion_bancaria": (False, True,  True),
    "periodos_cierre":       (False, True,  True),
    "activo_fijo":           (False, True,  True),
    "centros_costo":         (False, False, True),
    "situacion_financiera":  (False, True,  True),
    "analisis_cuentas":      (False, True,  True),
}

_INDICE = {p: i for i, p in enumerate(PERFILES)}


def visible(seccion: str, perfil: str | None) -> bool:
    """True si esa sección debe mostrarse para el perfil dado.

    Sin perfil elegido todavía (instalación recién abierta, antes de
    responder el asistente) se muestra todo — nunca tiene sentido ocultar
    algo antes de que el usuario haya podido decir qué prefiere.
    """
    if perfil not in _INDICE:
        return True
    return SECCIONES.get(seccion, (True, True, True))[_INDICE[perfil]]


def tope_empresas(perfil: str | None) -> int | None:
    """Cuántas empresas puede tener esta instalación. None = sin tope."""
    return TOPE_EMPRESAS.get(perfil)


def perfil_actual(db: Session) -> str | None:
    """El perfil elegido, o None si el asistente todavía no se respondió."""
    fila = db.scalar(
        select(Parametro).where(Parametro.empresa_id.is_(None), Parametro.clave == CLAVE)
    )
    return fila.valor if fila is not None and fila.valor in PERFILES else None


def elegir_perfil(db: Session, perfil: str) -> None:
    if perfil not in PERFILES:
        raise ValueError(f"Perfil desconocido: {perfil!r}")
    fila = db.scalar(
        select(Parametro).where(Parametro.empresa_id.is_(None), Parametro.clave == CLAVE)
    )
    if fila is None:
        db.add(Parametro(
            empresa_id=None, clave=CLAVE, valor=perfil,
            descripcion="Perfil de instalación (emprendedor/pyme/contador) — ver services/perfiles.py",
        ))
    else:
        fila.valor = perfil
    db.commit()
