"""Pruebas del arranque del ejecutable.

El .exe se compila con console=False, así que Windows no le asigna consola y
PyInstaller deja sys.stdout y sys.stderr en None. Estas pruebas reproducen esa
condición: sin ellas, el fallo sólo aparece al hacer doble clic sobre el .exe
(en el runner de CI el proceso sí recibe flujos reales y el error no se ve).
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-arranque-"))

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import run  # noqa: E402


class SinFlujos:
    """Contexto que deja sys.stdout y sys.stderr en None, como el .exe."""

    def __enter__(self):
        self._stdout, self._stderr = sys.stdout, sys.stderr
        sys.stdout = None
        sys.stderr = None
        return self

    def __exit__(self, *_excepcion):
        sys.stdout, sys.stderr = self._stdout, self._stderr
        return False


class TestFlujosAusentes(unittest.TestCase):
    def test_asegurar_flujos_los_repone(self):
        with SinFlujos():
            run.asegurar_flujos()
            repuesto_out, repuesto_err = sys.stdout, sys.stderr
        self.assertIsNotNone(repuesto_out)
        self.assertIsNotNone(repuesto_err)
        # Deben ser escribibles: cualquier librería puede volcar ahí.
        repuesto_out.write("prueba\n")
        self.assertTrue(hasattr(repuesto_out, "flush"))

    def test_no_toca_los_flujos_existentes(self):
        propio = io.StringIO()
        original = sys.stdout
        sys.stdout = propio
        try:
            run.asegurar_flujos()
            self.assertIs(sys.stdout, propio, "No debe reemplazar un stdout válido.")
        finally:
            sys.stdout = original

    def test_configurar_uvicorn_sin_consola(self):
        """Este es el fallo que rompía el .exe al abrirlo con doble clic.

        uvicorn.Config construye su formateador de logs con colores, que
        consulta sys.stdout.isatty(). Con stdout en None reventaba con
        «Unable to configure formatter 'default'».
        """
        import uvicorn

        with SinFlujos():
            run.asegurar_flujos()
            # No debe lanzar excepción.
            uvicorn.Config(
                object(), host="127.0.0.1", port=8799, log_level="warning",
                access_log=False, log_config=None, use_colors=False,
            )

    def test_servidor_se_construye_sin_consola(self):
        """El caso completo: crear el Servidor tal como lo hace main()."""
        with SinFlujos():
            run.asegurar_flujos()
            servidor = run.Servidor("127.0.0.1", 8798)
        self.assertTrue(servidor.url.endswith(":8798"))

    def test_print_no_falla_sin_consola(self):
        with SinFlujos():
            run.asegurar_flujos()
            print("mensaje de arranque")  # no debe lanzar


class TestPuertos(unittest.TestCase):
    def test_busca_un_puerto_libre(self):
        puerto = run.buscar_puerto("127.0.0.1", 8801)
        self.assertTrue(8801 <= puerto < 8841)
        self.assertTrue(run.puerto_disponible("127.0.0.1", puerto))

    def test_salta_los_puertos_ocupados(self):
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupado:
            ocupado.bind(("127.0.0.1", 8811))
            ocupado.listen(1)
            self.assertNotEqual(run.buscar_puerto("127.0.0.1", 8811), 8811)


class TestInformeDeError(unittest.TestCase):
    def test_deja_el_detalle_en_el_registro(self):
        with mock.patch.object(run, "RUTA_REGISTRO", Path(tempfile.mkdtemp()) / "log.txt"):
            with mock.patch.dict(sys.modules, {"tkinter": None}):
                run.informar_error(ValueError("algo se rompió"))
            texto = run.RUTA_REGISTRO.read_text(encoding="utf-8")
        self.assertIn("Error de arranque", texto)
        self.assertIn("algo se rompió", texto)
        self.assertIn("ValueError", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
