"""Pruebas del selector de cuentas con buscador (contaflow/static/buscable.js).

No hay un entorno de pruebas de JavaScript en este proyecto, así que se
comprueba por presencia de texto — igual que TestVolverUsaHistorial en
test_firma.py — en vez de ejecutar el script. Alcanza para no perder de
nuevo el aviso visual si alguien reescribe el archivo.
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BUSCABLE_JS = RAIZ / "contaflow" / "static" / "buscable.js"
ESTILOS_CSS = RAIZ / "contaflow" / "static" / "estilos.css"


class TestAvisoDeTextoSinCoincidencia(unittest.TestCase):
    """Antes de este aviso, escribir un texto que no calzaba con ninguna
    cuenta dejaba el campo con pinta de estar listo — el monto podía estar
    lleno y los totales cuadrar — pero la cuenta nunca quedaba seleccionada
    por debajo, y recién se sabía al guardar, con un error del servidor que
    no dice cuál línea falló."""

    def test_el_js_marca_el_campo_cuando_no_hay_coincidencia(self):
        js = BUSCABLE_JS.read_text(encoding="utf-8")
        self.assertIn("buscable-sin-coincidencia", js)
        # Se limpia el aviso apenas el texto vuelve a calzar con una opción.
        self.assertIn('classList.remove("buscable-sin-coincidencia")', js)

    def test_el_css_le_da_un_color_de_error_visible(self):
        css = ESTILOS_CSS.read_text(encoding="utf-8")
        self.assertIn(".buscable-sin-coincidencia", css)
        self.assertIn("var(--error)", css.split(".buscable-sin-coincidencia")[1][:200])


if __name__ == "__main__":
    unittest.main()
