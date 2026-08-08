"""Pruebas del manual de usuario en PDF.

Verifican que el diccionario de cuentas esté completo, que las referencias
cruzadas apunten a secciones reales y que el PDF salga con su índice
clickeable y sus marcadores bien enlazados.
"""
from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-manual-"))

from contaflow.services.glosario import GLOSARIO_CUENTAS, cuentas_sin_glosario  # noqa: E402
from contaflow.services.plan_cuentas import PLAN_CUENTAS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
GENERADOR = RAIZ / "herramientas" / "generar_manual.py"


class TestGlosarioCuentas(unittest.TestCase):
    def test_todas_las_cuentas_imputables_estan_documentadas(self):
        faltantes = cuentas_sin_glosario()
        self.assertEqual(
            faltantes, [],
            f"Estas cuentas del plan no tienen descripción en el glosario: {faltantes}",
        )

    def test_no_sobran_entradas(self):
        imputables = {c for c, _n, _t, i, _f in PLAN_CUENTAS if i}
        sobrantes = sorted(set(GLOSARIO_CUENTAS) - imputables)
        self.assertEqual(
            sobrantes, [],
            f"El glosario describe cuentas que no existen en el plan: {sobrantes}",
        )

    def test_cada_entrada_tiene_los_tres_campos(self):
        for codigo, valores in GLOSARIO_CUENTAS.items():
            with self.subTest(cuenta=codigo):
                self.assertEqual(len(valores), 3, "Se esperan uso, cargo y abono.")
                for texto in valores:
                    self.assertGreater(len(texto.strip()), 15,
                                       f"Descripción demasiado breve en {codigo}.")

    def test_las_cuentas_por_defecto_estan_documentadas(self):
        """Las cuentas que usan los asientos automáticos son las más consultadas."""
        from contaflow.services.plan_cuentas import CUENTAS_DEFECTO

        for clave, (codigo, _descripcion) in CUENTAS_DEFECTO.items():
            with self.subTest(parametro=clave):
                self.assertIn(codigo, GLOSARIO_CUENTAS)


class TestReferenciasCruzadas(unittest.TestCase):
    """Una referencia a una sección inexistente deja un enlace muerto en el PDF."""

    @classmethod
    def setUpClass(cls):
        cls.fuente = GENERADOR.read_text(encoding="utf-8")

    def test_toda_referencia_apunta_a_una_seccion_existente(self):
        definidas = set(re.findall(
            r'titulo\(\s*(?:f?"[^"]*"|[^,]+),\s*\d+\s*,\s*f?"([^"]+)"', self.fuente))
        usadas = set(re.findall(
            r'enlace\(\s*(?:f?"[^"]*"|f?\'[^\']*\')\s*,\s*"([^"]+)"\s*\)', self.fuente))
        usadas |= set(re.findall(
            r"enlace\(\s*(?:f?'[^']*'|f?\"[^\"]*\")\s*,\s*'([^']+)'\s*\)", self.fuente))

        self.assertGreater(len(usadas), 15, "Se esperaban referencias cruzadas en el manual.")
        rotas = sorted(usadas - definidas)
        self.assertEqual(rotas, [], f"Referencias a secciones inexistentes: {rotas}")


class TestGeneracionPDF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys

        sys.path.insert(0, str(RAIZ))
        from herramientas.generar_manual import construir

        cls.destino = Path(tempfile.mkdtemp(prefix="manual-")) / "Manual.pdf"
        construir(cls.destino)

    def test_el_pdf_se_genera(self):
        self.assertTrue(self.destino.exists())
        self.assertGreater(self.destino.stat().st_size, 80_000)
        self.assertEqual(self.destino.read_bytes()[:5], b"%PDF-")
        self.assertIn(b"%%EOF", self.destino.read_bytes()[-2048:])

    def test_estructura_e_hipervinculos(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf no está instalado (solo se usa para verificar el PDF)")

        lector = PdfReader(str(self.destino))
        self.assertGreater(len(lector.pages), 35, "El manual quedó demasiado corto.")

        paginas = {p.indirect_reference.idnum: i for i, p in enumerate(lector.pages, 1)}

        def pagina_destino(anotacion):
            d = anotacion.get("/Dest")
            if d is None and anotacion.get("/A"):
                d = anotacion["/A"].get_object().get("/D")
            if isinstance(d, list) and d:
                return paginas.get(getattr(d[0], "idnum", None))
            return None

        # --- Marcadores del panel lateral ---------------------------------
        marcadores = []

        def recorrer(items):
            for item in items:
                recorrer(item) if isinstance(item, list) else marcadores.append(item)

        recorrer(lector.outline)
        self.assertGreater(len(marcadores), 90, "Faltan marcadores en el panel del lector.")

        titulos = [str(m.title) for m in marcadores]
        self.assertIn("1. Bienvenido a ContaFlow", titulos)
        self.assertIn("4.3 Diccionario de cuentas", titulos)
        # Los títulos deben ser legibles, no la clave interna del ancla.
        internos = [t for t in titulos if re.fullmatch(r"(cap|grupo|anexo)[\w.-]*", t)]
        self.assertEqual(internos, [], f"Marcadores mostrando la clave interna: {internos}")

        destinos_marcador = [lector.get_destination_page_number(m) + 1 for m in marcadores]

        # --- Enlaces del índice -------------------------------------------
        indice, externos = [], 0
        for numero, pagina in enumerate(lector.pages, 1):
            for anot in (pagina.get("/Annots") or []):
                obj = anot.get_object()
                if obj.get("/Subtype") != "/Link":
                    continue
                accion = obj.get("/A")
                if accion and accion.get_object().get("/S") == "/URI":
                    externos += 1
                    continue
                destino = pagina_destino(obj)
                self.assertIsNotNone(
                    destino, f"Enlace sin destino resoluble en la página {numero}.")
                if 2 <= numero <= 5:  # páginas del índice
                    indice.append((-float(obj["/Rect"][3]), float(obj["/Rect"][0]),
                                   numero, destino))

        self.assertGreaterEqual(externos, 5, "Faltan los enlaces externos de los anexos.")

        # Cada entrada del índice genera dos anotaciones (el texto y el número
        # de página), así que se comparan de dos en dos contra los marcadores.
        indice.sort(key=lambda x: (x[2], x[0], x[1]))
        entradas = [d for _y, _x, _p, d in indice][::2]
        self.assertEqual(
            len(entradas), len(marcadores),
            "El índice y los marcadores no cubren las mismas secciones.",
        )
        descuadres = [
            (titulos[i], entradas[i], destinos_marcador[i])
            for i in range(len(entradas)) if entradas[i] != destinos_marcador[i]
        ]
        self.assertEqual(
            descuadres, [],
            f"Entradas del índice que saltan a la página equivocada: {descuadres[:5]}",
        )

    def test_contiene_el_diccionario_de_cuentas(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf no está instalado")

        lector = PdfReader(str(self.destino))
        texto = "".join((p.extract_text() or "") for p in lector.pages)
        for codigo in ("1.1.01.001", "2.1.03.001", "4.1.01.001", "5.2.03.001", "9.1.01.002"):
            with self.subTest(cuenta=codigo):
                self.assertIn(codigo, texto)
        self.assertIn("Diccionario de cuentas", texto)
        self.assertIn("Glosario de siglas", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
