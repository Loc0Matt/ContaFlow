"""Modo presentación: bloqueo global de escritura, para toda la instalación.

Pensado para cuando compartes pantalla con un cliente: lo activas y todo el
sistema queda en solo lectura — ningún formulario guarda, ninguna acción
modifica nada — sin importar qué usuario tenga la sesión iniciada. Como el
sistema es de un solo computador (nadie más puede estar usándolo al mismo
tiempo), es un interruptor único para toda la instalación, no por sesión.

El estado queda guardado en la base de datos (parámetro global), no en
memoria: si cierras el programa a mitad de una demo y lo vuelves a abrir,
sigue en modo presentación hasta que lo desactives a propósito.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.models import Parametro

CLAVE = "modo_presentacion"


def esta_activo(db: Session) -> bool:
    fila = db.scalar(
        select(Parametro).where(Parametro.empresa_id.is_(None), Parametro.clave == CLAVE)
    )
    return fila is not None and fila.valor == "1"


def activar(db: Session) -> None:
    _guardar(db, "1")


def desactivar(db: Session) -> None:
    _guardar(db, "0")


def alternar(db: Session) -> bool:
    """Cambia el estado actual y devuelve el nuevo valor."""
    if esta_activo(db):
        desactivar(db)
        return False
    activar(db)
    return True


def _guardar(db: Session, valor: str) -> None:
    fila = db.scalar(
        select(Parametro).where(Parametro.empresa_id.is_(None), Parametro.clave == CLAVE)
    )
    if fila is None:
        db.add(Parametro(
            empresa_id=None, clave=CLAVE, valor=valor,
            descripcion="Modo presentación (solo lectura) — 1 activo, 0 inactivo",
        ))
    else:
        fila.valor = valor
    db.commit()
