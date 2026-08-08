# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller para generar ContaFlow.exe (Windows).

Se construye con:  pyinstaller build/contaflow.spec --clean --noconfirm
El resultado queda en dist/ContaFlow.exe (un único archivo).
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

RAIZ = Path(SPECPATH).parent

# Plantillas y hoja de estilos viajan dentro del ejecutable; config.dir_recursos()
# los localiza en sys._MEIPASS cuando la app corre congelada.
datos = [
    (str(RAIZ / "contaflow" / "templates"), "contaflow/templates"),
    (str(RAIZ / "contaflow" / "static"), "contaflow/static"),
]

# Uvicorn y SQLAlchemy resuelven varios módulos en tiempo de ejecución,
# así que PyInstaller no los detecta con el análisis estático.
ocultos = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "sqlalchemy.dialects.sqlite",
    "email.mime.multipart",
    "email.mime.text",
]
ocultos += collect_submodules("contaflow")

analisis = Analysis(
    [str(RAIZ / "run.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=datos,
    hiddenimports=ocultos,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # PIL no se excluye: reportlab lo necesita para generar los PDF.
    excludes=["matplotlib", "numpy", "pandas", "scipy", "pytest", "IPython", "test"],
    noarchive=False,
)

pyz = PYZ(analisis.pure)

exe = EXE(
    pyz,
    analisis.scripts,
    analisis.binaries,
    analisis.datas,
    [],
    name="ContaFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # console=False deja sólo la ventana Tkinter, sin consola negra detrás.
    console=False,
    disable_windowed_traceback=False,
    icon=str(RAIZ / "build" / "contaflow.ico") if (RAIZ / "build" / "contaflow.ico").exists() else None,
    version=str(RAIZ / "build" / "version_info.txt")
    if (RAIZ / "build" / "version_info.txt").exists() else None,
)
