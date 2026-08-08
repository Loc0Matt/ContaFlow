"""Utilidades transversales: RUT chileno, montos, fechas y períodos."""
from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


# ---------------------------------------------------------------------------
# RUT
# ---------------------------------------------------------------------------


def limpiar_rut(rut: str | None) -> str:
    """Deja el RUT como dígitos + DV en mayúscula, sin puntos ni guion."""
    if not rut:
        return ""
    return re.sub(r"[^0-9kK]", "", rut).upper()


def digito_verificador(cuerpo: str) -> str:
    """Calcula el DV con el algoritmo módulo 11."""
    suma, multiplo = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplo
        multiplo = 2 if multiplo == 7 else multiplo + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def rut_valido(rut: str | None) -> bool:
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit():
        return False
    return digito_verificador(cuerpo) == dv


def formatear_rut(rut: str | None) -> str:
    """12345678K → 12.345.678-K"""
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return rut or ""
    cuerpo, dv = limpio[:-1], limpio[-1]
    partes = []
    while len(cuerpo) > 3:
        partes.insert(0, cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    partes.insert(0, cuerpo)
    return f"{'.'.join(partes)}-{dv}"


def normalizar_rut(rut: str | None) -> str:
    """Formato canónico de almacenamiento: 12345678-K"""
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return limpio
    return f"{limpio[:-1]}-{limpio[-1]}"


# ---------------------------------------------------------------------------
# Montos
# ---------------------------------------------------------------------------


def a_decimal(valor) -> Decimal:
    if valor is None or valor == "":
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, str):
        valor = valor.strip().replace("$", "").replace(" ", "")
        # Acepta 1.234.567,89 y 1234567.89
        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        elif valor.count(".") > 1:
            valor = valor.replace(".", "")
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return Decimal("0")


def redondear(valor, decimales: int = 0) -> float:
    """Redondeo comercial (half-up), el que usa el SII para el IVA."""
    exp = Decimal(1).scaleb(-decimales)
    return float(a_decimal(valor).quantize(exp, rounding=ROUND_HALF_UP))


def pesos(valor) -> int:
    """Los montos en CLP se manejan como enteros."""
    return int(redondear(valor, 0))


def formato_moneda(valor, simbolo: bool = True) -> str:
    numero = pesos(valor)
    texto = f"{abs(numero):,}".replace(",", ".")
    signo = "-" if numero < 0 else ""
    return f"{signo}${texto}" if simbolo else f"{signo}{texto}"


def formato_decimal(valor, decimales: int = 2) -> str:
    numero = float(a_decimal(valor))
    texto = f"{abs(numero):,.{decimales}f}"
    texto = texto.replace(",", "@").replace(".", ",").replace("@", ".")
    return ("-" if numero < 0 else "") + texto


# ---------------------------------------------------------------------------
# Fechas y períodos
# ---------------------------------------------------------------------------


def rango_mes(anio: int, mes: int) -> tuple[date, date]:
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo)


def nombre_mes(mes: int) -> str:
    return MESES[mes] if 1 <= mes <= 12 else str(mes)


def periodo_etiqueta(anio: int, mes: int) -> str:
    return f"{nombre_mes(mes)} {anio}"


def mes_anterior(anio: int, mes: int) -> tuple[int, int]:
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def parse_fecha(texto: str | None, defecto: date | None = None) -> date | None:
    if not texto:
        return defecto
    if isinstance(texto, date):
        return texto
    for patron in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(texto.strip(), patron).date()
        except ValueError:
            continue
    return defecto


def formato_fecha(valor: date | None) -> str:
    return valor.strftime("%d-%m-%Y") if valor else ""


def slug(texto: str) -> str:
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", (texto or "").strip().lower())
    return limpio.strip("-") or "archivo"
