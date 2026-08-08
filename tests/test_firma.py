"""Pruebas del sello de autoría.

Si alguien borra o altera la firma, estas pruebas fallan y dejan constancia.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-firma-"))

from contaflow.firma import (  # noqa: E402
    HUELLA, autor, huella_actual, intacto, linea_credito, marca_agua, sello,
)

RAIZ = Path(__file__).resolve().parent.parent
AUTOR = "Loc0Matt"


class TestSello(unittest.TestCase):
    def test_el_sello_esta_intacto(self):
        self.assertTrue(intacto(), "La huella no coincide: el sello fue alterado.")
        self.assertEqual(huella_actual(), HUELLA)

    def test_contiene_los_datos_de_autoria(self):
        d = sello()
        self.assertEqual(d["autor"], AUTOR)
        self.assertEqual(d["proyecto"], "ContaFlow")
        self.assertEqual(d["licencia"], "MIT")
        self.assertIn("Loc0Matt", d["repositorio"])

    def test_atajos(self):
        self.assertEqual(autor(), AUTOR)
        self.assertIn(AUTOR, linea_credito())
        self.assertIn(AUTOR, marca_agua())
        self.assertIn(HUELLA[:16], marca_agua())


class TestSelloIncrustado(unittest.TestCase):
    """El sello debe estar en varios sitios, no en uno solo."""

    def test_licencia_y_autores(self):
        licencia = (RAIZ / "LICENSE").read_text(encoding="utf-8")
        self.assertIn(AUTOR, licencia)
        self.assertIn("MIT", licencia)
        self.assertIn(AUTOR, (RAIZ / "AUTORES.md").read_text(encoding="utf-8"))

    def test_metadatos_del_ejecutable(self):
        info = (RAIZ / "build" / "version_info.txt").read_text(encoding="utf-8")
        self.assertIn(AUTOR, info)
        self.assertIn("LegalCopyright", info)

    def test_plantilla_base(self):
        base = (RAIZ / "contaflow" / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn('name="author"', base)
        self.assertIn("FIRMA_CREDITO", base)

    def test_ruta_oculta_y_html(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("httpx no está instalado")

        from contaflow.app import crear_app

        cliente = TestClient(crear_app())

        # La ruta /firma responde sin necesidad de iniciar sesión.
        datos = cliente.get("/firma").json()
        self.assertEqual(datos["autor"], AUTOR)
        self.assertTrue(datos["intacto"])
        self.assertEqual(datos["huella"], HUELLA)

        # Y el sello viaja en el HTML de cualquier página.
        html = cliente.get("/login").text
        self.assertIn(AUTOR, html)

    def test_sello_en_la_base_de_datos(self):
        from sqlalchemy import select

        from contaflow.database import SessionLocal, crear_esquema
        from contaflow.models import Parametro
        from contaflow.services.seed import sembrar_globales

        crear_esquema()
        with SessionLocal() as db:
            sembrar_globales(db)
            guardado = db.scalar(
                select(Parametro).where(Parametro.clave == "sello_autoria")
            )
            self.assertIsNotNone(guardado, "El sello no quedó registrado en la base.")
            self.assertIn(AUTOR, guardado.valor)


class TestSinAtribucionAutomatica(unittest.TestCase):
    """El código no debe mencionar herramientas de generación automática."""

    PROHIBIDAS = ("claude", "anthropic", "copilot", "chatgpt", "openai",
                  "co-authored-by", "generated with")

    def test_el_codigo_esta_limpio(self):
        propio = Path(__file__).resolve()
        sospechosos = []
        for ruta in RAIZ.rglob("*"):
            if not ruta.is_file():
                continue
            if ruta.resolve() == propio:
                continue  # este archivo contiene los términos a propósito
            partes = ruta.parts
            if any(p in (".git", ".venv", "dist", "build", "__pycache__") for p in partes):
                continue
            if ruta.suffix.lower() in (".pdf", ".png", ".ico", ".db", ".xlsx"):
                continue
            try:
                texto = ruta.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            for termino in self.PROHIBIDAS:
                if termino in texto:
                    sospechosos.append(f"{ruta.relative_to(RAIZ)} → «{termino}»")
        self.assertEqual(sospechosos, [], f"Atribución automática encontrada: {sospechosos}")



class TestLogotipo(unittest.TestCase):
    """El sistema debe funcionar con o sin logotipo propio."""

    def test_siempre_hay_un_logo(self):
        from contaflow.marca import ruta_logo, url_logo

        self.assertIsNotNone(ruta_logo(), "Falta incluso el escudo de reserva.")
        self.assertEqual(url_logo(), "/logo")

    def test_el_escudo_de_reserva_existe(self):
        reserva = RAIZ / "contaflow" / "static" / "logo-generico.svg"
        self.assertTrue(reserva.is_file())
        self.assertIn("<svg", reserva.read_text(encoding="utf-8"))

    def test_prioridad_del_logo_propio(self):
        """Si el usuario deja su logo, manda sobre el escudo de reserva."""
        import contaflow.marca as marca

        propio = marca.DIR_STATIC / "logo.png"
        creado = False
        try:
            if not propio.exists():
                # PNG mínimo válido de 1x1 píxel.
                propio.write_bytes(bytes.fromhex(
                    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
                    "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
                ))
                creado = True
            marca.ruta_logo.cache_clear()
            self.assertEqual(marca.ruta_logo().name, "logo.png")
            self.assertTrue(marca.es_personalizado())
            self.assertIsNotNone(marca.ruta_rasterizada())
        finally:
            if creado:
                propio.unlink()
            marca.ruta_logo.cache_clear()

    def test_el_logo_llega_al_html(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("httpx no está instalado")

        from contaflow.app import crear_app

        cliente = TestClient(crear_app())
        html = cliente.get("/login").text
        self.assertIn('rel="icon"', html)
        self.assertIn("/logo", html)

        # La ruta /logo entrega una imagen real, sin necesidad de iniciar sesión.
        respuesta = cliente.get("/logo")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.headers["content-type"].startswith("image/"))
        self.assertGreater(len(respuesta.content), 500)

if __name__ == "__main__":
    unittest.main(verbosity=2)
