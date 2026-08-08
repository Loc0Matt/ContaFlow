"""Identidad visual: resuelve el logotipo que usa la aplicación.

Si existe `contaflow/static/logo.png` (o .jpg / .svg), se usa ese. Si no, se
recurre al escudo genérico incluido en `contaflow/static/logo.svg`.

Para poner tu propio logo basta con dejar el archivo en esa carpeta: la
interfaz, el favicon, la portada del manual y el icono del ejecutable lo
toman automáticamente.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from contaflow.config import DIR_STATIC

#: Orden de preferencia. El primero que exista es el que manda.
NOMBRES = ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp", "logo.svg")

#: Escudo genérico de reserva, incluido siempre en el repositorio.
RESERVA = "logo-generico.svg"


@lru_cache(maxsize=1)
def ruta_logo() -> Path | None:
    """Ruta al archivo de logotipo activo, o None si no hay ninguno."""
    for nombre in NOMBRES:
        candidato = DIR_STATIC / nombre
        if candidato.is_file() and candidato.stat().st_size > 0:
            return candidato
    reserva = DIR_STATIC / RESERVA
    return reserva if reserva.is_file() else None


def url_logo() -> str:
    """URL que sirve el logotipo dentro de la aplicación."""
    ruta = ruta_logo()
    return f"/static/{ruta.name}" if ruta else ""


def es_personalizado() -> bool:
    """True cuando hay un logo propio, no el escudo de reserva."""
    ruta = ruta_logo()
    return bool(ruta and ruta.name != RESERVA)


def ruta_rasterizada() -> Path | None:
    """Logotipo en formato de imagen (no vectorial), para el PDF y el icono.

    reportlab y Pillow no leen SVG, así que sólo sirven PNG/JPG/WEBP.
    """
    ruta = ruta_logo()
    if ruta and ruta.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return ruta
    return None
