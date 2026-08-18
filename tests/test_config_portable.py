"""Pruebas del modo portable: datos junto al .exe (contaflow/config.py)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-portable-"))

import contaflow.config as cfg  # noqa: E402


class TestCarpetaPortable(unittest.TestCase):
    def test_no_aplica_sin_estar_congelado(self):
        """python run.py (desarrollo): nunca es portable, aunque exista la carpeta."""
        with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=False):
            self.assertIsNone(cfg.dir_datos_portable())

    def test_none_si_no_existe_la_carpeta_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContaFlow.exe"
            exe.touch()
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    self.assertIsNone(cfg.dir_datos_portable())

    def test_usa_la_carpeta_datos_si_existe_junto_al_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContaFlow.exe"
            exe.touch()
            (Path(tmp) / "datos").mkdir()
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    portable = cfg.dir_datos_portable()
            self.assertEqual(portable, Path(tmp) / "datos")

    def test_dir_datos_prioriza_contaflow_data_sobre_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContaFlow.exe"
            exe.touch()
            (Path(tmp) / "datos").mkdir()
            explicita = Path(tempfile.mkdtemp(prefix="contaflow-explicita-"))
            with mock.patch.dict(os.environ, {"CONTAFLOW_DATA": str(explicita)}):
                with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                    with mock.patch.object(sys, "executable", str(exe)):
                        resultado = cfg.dir_datos()
            self.assertEqual(resultado, explicita)

    def test_dir_datos_usa_portable_cuando_existe_la_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContaFlow.exe"
            exe.touch()
            (Path(tmp) / "datos").mkdir()
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CONTAFLOW_DATA", None)
                with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                    with mock.patch.object(sys, "executable", str(exe)):
                        resultado = cfg.dir_datos()
            self.assertEqual(resultado, Path(tmp) / "datos")

    def test_instalacion_existente_sigue_en_appdata_si_no_crea_la_carpeta(self):
        """El caso que no debe romperse nunca: alguien que ya usa ContaFlow
        (datos en AppData) actualiza el .exe. Sin la carpeta `datos` de
        manera explícita, sigue exactamente igual que antes — nunca "pierde"
        sus datos por quedar apuntando a una carpeta portable vacía."""
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContaFlow.exe"
            exe.touch()
            # Sin carpeta "datos" creada.
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    self.assertIsNone(cfg.dir_datos_portable())


if __name__ == "__main__":
    unittest.main(verbosity=2)
