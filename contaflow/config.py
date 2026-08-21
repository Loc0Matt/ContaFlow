"""Configuración global de ContAll.

Mantiene rutas de datos, parámetros tributarios y previsionales chilenos.
Los valores por defecto son editables desde la interfaz (tabla `parametro`),
esto sólo define el punto de partida.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ContAll"
APP_TITULO = "ContAll · Contabilidad para Todos"
APP_VERSION = "1.1.2"

#: Nombre anterior del programa (hasta la v1.0.0). Se usa sólo para que
#: quien ya lo tenía instalado no "pierda" sus datos al actualizar — ver
#: `dir_datos_legado()`.
_NOMBRE_ANTERIOR = "ContaFlow"


def es_ejecutable_congelado() -> bool:
    """True cuando corremos dentro del .exe generado por PyInstaller."""
    return getattr(sys, "frozen", False)


def dir_recursos() -> Path:
    """Directorio de recursos de solo lectura (templates, static)."""
    if es_ejecutable_congelado():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _carpeta_appdata(nombre: str) -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / nombre
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / nombre


def _hay_datos_en_appdata() -> bool:
    """True si ya existe una base de datos en AppData/XDG, con el nombre
    actual o el anterior a la v1.1.0 — para no crearle de golpe una carpeta
    portable vacía junto al `.exe` a quien ya tiene datos guardados ahí."""
    return any(
        (_carpeta_appdata(nombre) / "contaflow.db").is_file()
        for nombre in (APP_NAME, _NOMBRE_ANTERIOR)
    )


def dir_datos_portable() -> Path | None:
    """Carpeta `datos` junto al propio `.exe`.

    En una instalación realmente nueva (nada guardado todavía en AppData,
    ni con el nombre actual ni con el anterior) el propio `.exe` la crea
    solo la primera vez que arranca — así el caso más común, «bajo el .exe
    y lo uso», queda portable de fábrica sin ningún paso manual: basta con
    copiar esa misma carpeta si se quiere mover a otro computador.

    Sigue siendo opt-in para quien YA tiene datos en AppData (con el
    nombre actual o el anterior a la v1.1.0): ahí no se crea nada acá y el
    arranque sigue leyendo AppData exactamente como antes — nunca se
    «pierden» datos ya guardados sólo por reemplazar el `.exe`. Esa
    persona puede seguir activando el modo portable ella misma, creando
    la carpeta `datos` a mano, como siempre.

    Sólo aplica al ejecutable congelado; en desarrollo (`python run.py`)
    no tendría sentido.
    """
    if not es_ejecutable_congelado():
        return None
    carpeta = Path(sys.executable).resolve().parent / "datos"
    if carpeta.is_dir():
        return carpeta
    if _hay_datos_en_appdata():
        return None
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None  # sin permiso de escritura junto al .exe: sigue en AppData
    return carpeta


def dir_datos_legado() -> Path | None:
    """Carpeta AppData/XDG de la v1.0.0, cuando el programa se llamaba
    ContaFlow — sólo si de verdad tiene datos adentro.

    Con el cambio de nombre a ContAll (v1.1.0), la carpeta por defecto pasa
    de `.../ContaFlow` a `.../ContAll`. Sin este empalme, quien actualice el
    `.exe` abriría un sistema aparentemente vacío la primera vez, con sus
    empresas y comprobantes "perdidos" en la carpeta vieja. Se comprueba que
    exista `contaflow.db` (no sólo la carpeta) para no adoptar por error una
    carpeta `ContaFlow` vacía o de otra cosa.
    """
    carpeta = _carpeta_appdata(_NOMBRE_ANTERIOR)
    return carpeta if (carpeta / "contaflow.db").is_file() else None


def dir_datos() -> Path:
    """Carpeta de datos del usuario. Persiste entre actualizaciones del .exe."""
    if os.environ.get("CONTAFLOW_DATA"):
        base = Path(os.environ["CONTAFLOW_DATA"])
    elif dir_datos_portable() is not None:
        base = dir_datos_portable()
    elif not es_ejecutable_congelado():
        base = _carpeta_appdata(APP_NAME)
    else:
        base = dir_datos_legado() or _carpeta_appdata(APP_NAME)
    base.mkdir(parents=True, exist_ok=True)
    return base


DIR_BASE = dir_recursos()
DIR_DATOS = dir_datos()
DIR_TEMPLATES = DIR_BASE / "contaflow" / "templates"
DIR_STATIC = DIR_BASE / "contaflow" / "static"
#: Manual de usuario en PDF, incrustado en el propio .exe (ver build/contaflow.spec)
#: para que esté disponible sin depender de bajarlo aparte de las Releases.
RUTA_MANUAL = DIR_BASE / "docs" / "Manual-ContAll.pdf"
DIR_BACKUPS = DIR_DATOS / "respaldos"
DIR_EXPORT = DIR_DATOS / "exportaciones"
for _d in (DIR_BACKUPS, DIR_EXPORT):
    _d.mkdir(parents=True, exist_ok=True)

RUTA_BD = DIR_DATOS / "contaflow.db"
URL_BD = os.environ.get("CONTAFLOW_DB_URL", f"sqlite:///{RUTA_BD}")

HOST = os.environ.get("CONTAFLOW_HOST", "127.0.0.1")
PUERTO = int(os.environ.get("CONTAFLOW_PORT", "8777"))

# ---------------------------------------------------------------------------
# Parámetros tributarios
# ---------------------------------------------------------------------------

TASA_IVA = 0.19

#: Retención de honorarios de segunda categoría — Ley 21.133 (aumento gradual).
RETENCION_HONORARIOS = {
    2019: 0.1000, 2020: 0.1075, 2021: 0.1150, 2022: 0.1225, 2023: 0.1300,
    2024: 0.1375, 2025: 0.1450, 2026: 0.1525, 2027: 0.1600, 2028: 0.1700,
}
RETENCION_HONORARIOS_DEFECTO = 0.1725  # 2029 en adelante

#: Tabla de Impuesto Único de Segunda Categoría, expresada en UTM.
#: (desde, hasta, factor, rebaja) — `hasta = None` es el último tramo.
TABLA_IMPUESTO_UNICO_UTM = [
    (0.0, 13.5, 0.000, 0.00),
    (13.5, 30.0, 0.040, 0.54),
    (30.0, 50.0, 0.080, 1.74),
    (50.0, 70.0, 0.135, 4.49),
    (70.0, 90.0, 0.230, 11.14),
    (90.0, 120.0, 0.304, 17.80),
    (120.0, 310.0, 0.350, 23.32),
    (310.0, None, 0.400, 38.82),
]

#: Impuesto Global Complementario anual, expresado en UTA (misma escala anualizada).
TABLA_GLOBAL_COMPLEMENTARIO_UTA = TABLA_IMPUESTO_UNICO_UTM

# ---------------------------------------------------------------------------
# Parámetros previsionales (editables en Configuración → Previsional)
# ---------------------------------------------------------------------------

TOPE_IMPONIBLE_AFP_UF = 87.8
TOPE_IMPONIBLE_SALUD_UF = 87.8
TOPE_IMPONIBLE_AFC_UF = 131.9
TASA_SALUD_LEGAL = 0.07
TASA_SIS_EMPLEADOR = 0.0188

TASAS_AFC = {
    # tipo de contrato: (tasa trabajador, tasa empleador seguro cesantía)
    "INDEFINIDO": (0.006, 0.024),
    "PLAZO_FIJO": (0.000, 0.030),
    "OBRA_FAENA": (0.000, 0.030),
}

#: Cotización obligatoria AFP = 10% capitalización + comisión de la administradora.
AFP_DEFECTO = [
    ("CAPITAL", 11.44),
    ("CUPRUM", 11.44),
    ("HABITAT", 11.27),
    ("MODELO", 10.58),
    ("PLANVITAL", 11.16),
    ("PROVIDA", 11.45),
    ("UNO", 10.69),
]

#: Gratificación legal Art. 50 Código del Trabajo: 25% de lo devengado
#: con tope de 4,75 ingresos mínimos mensuales al año.
GRATIFICACION_PORCENTAJE = 0.25
GRATIFICACION_TOPE_IMM = 4.75

def _obtener_o_crear_secreto_sesion() -> str:
    """Clave de firma de las cookies de sesión: aleatoria y persistida.

    Antes se derivaba de la ruta de la base de datos — predecible, y la
    misma para cualquier instalación del mismo usuario de Windows. Ahora se
    genera una sola vez con secrets.token_hex() y se guarda en un archivo
    dentro de la carpeta de datos, para que sobreviva a que se reemplace el
    .exe por una versión nueva.
    """
    import secrets

    archivo = DIR_DATOS / "session.key"
    try:
        clave = archivo.read_text(encoding="utf-8").strip()
        if clave:
            return clave
    except OSError:
        pass

    clave = secrets.token_hex(32)
    try:
        archivo.write_text(clave, encoding="utf-8")
    except OSError:
        pass  # sin permiso de escritura: mejor una clave nueva cada arranque que romper
    return clave


SESSION_SECRET = os.environ.get("CONTAFLOW_SECRET") or _obtener_o_crear_secreto_sesion()
