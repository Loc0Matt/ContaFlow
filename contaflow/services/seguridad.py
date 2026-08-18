"""Hash de contraseñas y helpers de sesión (sin dependencias externas)."""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta

ITERACIONES = 200_000

#: Intentos de login fallidos permitidos antes de bloquear temporalmente.
MAX_INTENTOS_LOGIN = 5
#: Minutos que dura el bloqueo una vez alcanzado el máximo.
BLOQUEO_MINUTOS = 15


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${salt.hex()}${dk.hex()}"


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        algoritmo, iteraciones, salt_hex, hash_hex = almacenado.split("$")
    except ValueError:
        return False
    if algoritmo != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), int(iteraciones)
    )
    return hmac.compare_digest(dk.hex(), hash_hex)


def cuenta_bloqueada(bloqueado_hasta: datetime | None, ahora: datetime | None = None) -> bool:
    """True mientras el bloqueo temporal por intentos fallidos siga vigente."""
    ahora = ahora or datetime.now()
    return bloqueado_hasta is not None and bloqueado_hasta > ahora


def registrar_intento_fallido(
    intentos_fallidos: int, ahora: datetime | None = None
) -> tuple[int, datetime | None]:
    """Suma un intento fallido; devuelve (intentos_nuevos, bloqueado_hasta).

    `bloqueado_hasta` es None mientras no se alcance el máximo — recién ahí
    se fija el bloqueo temporal, contado desde `ahora`.
    """
    ahora = ahora or datetime.now()
    intentos = intentos_fallidos + 1
    if intentos >= MAX_INTENTOS_LOGIN:
        return intentos, ahora + timedelta(minutes=BLOQUEO_MINUTOS)
    return intentos, None


def validar_password(password: str, minimo: int = 8) -> str | None:
    """Devuelve un mensaje de error si la contraseña no cumple el mínimo, o
    None si es válida. Centraliza la regla para no repetirla en cada lugar
    que crea o cambia una contraseña."""
    if len(password) < minimo:
        return f"La contraseña debe tener al menos {minimo} caracteres."
    return None
