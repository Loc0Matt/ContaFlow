"""Pruebas de la clave de firma de sesión (P1-3): aleatoria y persistida.

Usa su propia carpeta de datos temporal — no depende del CONTAFLOW_DATA que
fijan otros archivos de prueba al importarse, porque necesita controlar
exactamente dónde queda `session.key`.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-secreto-"))

import contaflow.config as cfg  # noqa: E402


class TestSecretoDeSesion(unittest.TestCase):
    def _carpeta_temporal(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="contaflow-secreto-datos-"))

    def test_genera_una_clave_larga_y_aleatoria(self):
        with mock.patch.object(cfg, "DIR_DATOS", self._carpeta_temporal()):
            clave = cfg._obtener_o_crear_secreto_sesion()
        self.assertEqual(len(clave), 64)  # secrets.token_hex(32) -> 64 hex chars
        int(clave, 16)  # no lanza: es hexadecimal válido

    def test_persiste_entre_llamadas(self):
        with mock.patch.object(cfg, "DIR_DATOS", self._carpeta_temporal()):
            primera = cfg._obtener_o_crear_secreto_sesion()
            segunda = cfg._obtener_o_crear_secreto_sesion()
        self.assertEqual(primera, segunda)

    def test_dos_instalaciones_distintas_tienen_claves_distintas(self):
        with mock.patch.object(cfg, "DIR_DATOS", self._carpeta_temporal()):
            clave_a = cfg._obtener_o_crear_secreto_sesion()
        with mock.patch.object(cfg, "DIR_DATOS", self._carpeta_temporal()):
            clave_b = cfg._obtener_o_crear_secreto_sesion()
        self.assertNotEqual(clave_a, clave_b)

    def test_queda_guardada_en_session_key(self):
        carpeta = self._carpeta_temporal()
        with mock.patch.object(cfg, "DIR_DATOS", carpeta):
            clave = cfg._obtener_o_crear_secreto_sesion()
        archivo = carpeta / "session.key"
        self.assertTrue(archivo.exists())
        self.assertEqual(archivo.read_text(encoding="utf-8").strip(), clave)

    def test_no_depende_de_la_ruta_de_la_base_de_datos(self):
        """El bug original: el secreto se derivaba de RUTA_BD, así que dos
        instalaciones con la misma ruta (mismo usuario de Windows) tenían la
        misma clave, adivinable. Ahora no debe guardar relación alguna."""
        with mock.patch.object(cfg, "DIR_DATOS", self._carpeta_temporal()):
            clave = cfg._obtener_o_crear_secreto_sesion()
        self.assertNotIn(str(cfg.RUTA_BD), clave)
        self.assertNotIn("contaflow-local", clave)

    def test_variable_de_entorno_tiene_prioridad(self):
        """CONTAFLOW_SECRET, si está definida, sigue ganando (para despliegues
        avanzados) sin tocar el archivo persistido."""
        with mock.patch.dict(os.environ, {"CONTAFLOW_SECRET": "mi-secreto-explicito"}):
            secreto = os.environ.get("CONTAFLOW_SECRET") or cfg._obtener_o_crear_secreto_sesion()
        self.assertEqual(secreto, "mi-secreto-explicito")

    def test_archivo_vacio_o_corrupto_se_regenera(self):
        carpeta = self._carpeta_temporal()
        (carpeta / "session.key").write_text("", encoding="utf-8")
        with mock.patch.object(cfg, "DIR_DATOS", carpeta):
            clave = cfg._obtener_o_crear_secreto_sesion()
        self.assertEqual(len(clave), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
