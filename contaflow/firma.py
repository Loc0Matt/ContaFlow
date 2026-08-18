"""Sello de autoría de ContAll.

El proyecto es de código abierto (licencia MIT): cualquiera puede usarlo,
modificarlo o comercializarlo, siempre que conserve el aviso de copyright.
Este módulo deja constancia verificable de quién lo escribió.

El sello va codificado en base64 —no cifrado— para que no aparezca en una
búsqueda de texto superficial, pero siga siendo auditable por cualquiera:

    python -m contaflow.firma

La huella SHA-256 permite detectar si alguien alteró el contenido del sello.
"""
from __future__ import annotations

import base64
import hashlib
import json

#: Datos de autoría en base64 (JSON con claves ordenadas).
_SELLO = (
    "eyJhbmlvIjoyMDI2LCJhdXRvciI6IkxvYzBNYXR0IiwiY29udGFjdG8iOiJtYXRpLnNvdG85OEBnbWFpbC5"
    "jb20iLCJkZXNjcmlwY2lvbiI6IlNpc3RlbWEgY29udGFibGUgY2hpbGVubyBtdWx0aWVtcHJlc2EgXHUyMD"
    "E0IGNvbnRhYmlsaWRhZCBwYXJhIHRvZG9zIiwibGljZW5jaWEiOiJNSVQiLCJwcm95ZWN0byI6IkNvbnRBb"
    "GwiLCJyZXBvc2l0b3JpbyI6ImdpdGh1Yi5jb20vTG9jME1hdHQvQ29udGFGbG93In0="
)

#: SHA-256 del JSON original. Si el sello se altera, deja de coincidir.
HUELLA = "1f19723588daef7a4c852f3719b7c87998f40b5bea775bfa04f2498e2bb72373"


def sello() -> dict:
    """Devuelve los datos de autoría decodificados."""
    return json.loads(base64.b64decode(_SELLO))


def autor() -> str:
    return sello()["autor"]


def huella_actual() -> str:
    return hashlib.sha256(base64.b64decode(_SELLO)).hexdigest()


def intacto() -> bool:
    """True si el sello no ha sido modificado."""
    return huella_actual() == HUELLA


def linea_credito() -> str:
    """Una línea de crédito lista para mostrar o incrustar."""
    d = sello()
    return (
        f"{d['proyecto']} — {d['descripcion']}. "
        f"Creado por {d['autor']} ({d['anio']}). Licencia {d['licencia']}."
    )


def marca_agua() -> str:
    """Cadena compacta para incrustar en archivos generados y en la base de datos."""
    d = sello()
    return f"{d['proyecto']}/{d['anio']} · autor:{d['autor']} · {HUELLA[:16]}"


def _informe() -> str:
    d = sello()
    ancho = max(len(k) for k in d)
    filas = "\n".join(f"  {k.ljust(ancho)} : {v}" for k, v in sorted(d.items()))
    estado = "íntegro" if intacto() else "¡ALTERADO!"
    return (
        "Sello de autoría de ContAll\n"
        "=============================\n"
        f"{filas}\n"
        f"  {'huella'.ljust(ancho)} : {HUELLA}\n"
        f"  {'estado'.ljust(ancho)} : {estado}\n"
    )


if __name__ == "__main__":  # pragma: no cover
    print(_informe())
