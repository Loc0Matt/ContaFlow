"""Hash de contraseñas y helpers de sesión (sin dependencias externas)."""
from __future__ import annotations

import hashlib
import hmac
import os

ITERACIONES = 200_000


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
