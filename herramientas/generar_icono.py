"""Genera build/contaflow.ico a partir del logotipo, para el icono del .exe.

Si no hay un logotipo rasterizado (PNG/JPG) en contaflow/static/, no hace
nada: PyInstaller usará entonces el icono por defecto.

    python herramientas/generar_icono.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaflow.marca import recortar_margenes, ruta_rasterizada  # noqa: E402

#: Windows usa el tamaño que mejor le calce según el contexto.
TAMANOS = [(n, n) for n in (16, 24, 32, 48, 64, 128, 256)]


def construir(destino: Path | None = None) -> Path | None:
    origen = ruta_rasterizada()
    if origen is None:
        print("No hay logotipo rasterizado en contaflow/static/: se omite el icono.")
        return None

    from PIL import Image

    destino = destino or RAIZ / "build" / "contaflow.ico"
    with Image.open(origen) as original:
        # Sin recortar el margen, el icono se ve minúsculo en la barra de tareas.
        img = recortar_margenes(original).convert("RGBA")
        # El icono debe ser cuadrado: se centra sobre un lienzo transparente.
        lado = max(img.size)
        lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        lienzo.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2), img)
        lienzo.save(destino, format="ICO", sizes=TAMANOS)

    print(f"Icono generado desde {origen.name}: {destino} ({destino.stat().st_size // 1024} KB)")
    return destino


if __name__ == "__main__":
    construir()
