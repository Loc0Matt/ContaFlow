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

from contaflow.config import DIR_DATOS, DIR_STATIC

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
    return "/logo" if ruta_logo() else ""


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


def recortar_margenes(imagen):
    """Quita el margen uniforme que rodea al logotipo.

    Los logos suelen venir centrados en un lienzo cuadrado con mucho espacio
    en blanco; sin recortarlo se ven diminutos. Devuelve la misma imagen si no
    hay nada que recortar.
    """
    from PIL import ImageChops

    if imagen.mode in ("RGBA", "LA"):
        caja = imagen.getchannel("A").getbbox()
        if caja:
            return imagen.crop(caja)
        imagen = imagen.convert("RGB")

    rgb = imagen.convert("RGB")
    from PIL import Image as PILImage

    # El color de la esquina superior izquierda se toma como fondo.
    fondo = PILImage.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    caja = ImageChops.difference(rgb, fondo).getbbox()
    return imagen.crop(caja) if caja else imagen


def logo_recortado(destino: Path) -> Path | None:
    """Genera (y cachea) una versión del logotipo sin márgenes.

    Se regenera sólo si el original cambió. Ante cualquier problema devuelve
    el archivo original, para no dejar la aplicación sin logo.
    """
    origen = ruta_rasterizada()
    if origen is None:
        return None
    try:
        if destino.exists() and destino.stat().st_mtime >= origen.stat().st_mtime:
            return destino
        from PIL import Image as PILImage

        destino.parent.mkdir(parents=True, exist_ok=True)
        with PILImage.open(origen) as img:
            recortar_margenes(img).save(destino, format="PNG")
        return destino
    except Exception:
        return origen


#: Copia recortada que sirve la aplicación (la carpeta de datos sí es escribible;
#: dentro del .exe los recursos son de sólo lectura).
CACHE = DIR_DATOS / "logo-recortado.png"


def archivo_a_servir() -> tuple[Path, str] | None:
    """(ruta, tipo MIME) del logotipo que entrega la ruta /logo."""
    recortado = logo_recortado(CACHE)
    if recortado is not None:
        return recortado, "image/png"
    ruta = ruta_logo()
    if ruta is None:
        return None
    tipos = {".svg": "image/svg+xml", ".png": "image/png",
             ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    return ruta, tipos.get(ruta.suffix.lower(), "application/octet-stream")
