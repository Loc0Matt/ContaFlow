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

    def test_crea_la_carpeta_datos_sola_en_instalacion_nueva(self):
        """Instalación realmente nueva (nada en AppData todavía, ni con el
        nombre actual ni con el anterior): el .exe crea `datos` solo, sin
        que haya que hacerlo a mano."""
        with tempfile.TemporaryDirectory() as tmp:
            # .resolve(): en Windows, tempfile puede devolver la ruta con un
            # nombre corto 8.3 (p.ej. RUNNER~1) — Path(sys.executable).resolve()
            # en config.py la expande al nombre largo, así que sin esto la
            # comparación de abajo falla aunque sea exactamente la misma
            # carpeta física.
            tmp = Path(tmp).resolve()
            exe = tmp / "ContAll.exe"
            exe.touch()
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    with mock.patch.object(cfg, "_hay_datos_en_appdata", return_value=False):
                        portable = cfg.dir_datos_portable()
            self.assertEqual(portable, Path(tmp) / "datos")
            self.assertTrue((Path(tmp) / "datos").is_dir())

    def test_no_crea_la_carpeta_si_ya_hay_datos_en_appdata(self):
        """Quien ya tiene datos guardados en AppData (nombre actual o el
        anterior) no se lleva de sorpresa una carpeta portable vacía junto
        al .exe: sigue en AppData, tal como antes de este cambio."""
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContAll.exe"
            exe.touch()
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    with mock.patch.object(cfg, "_hay_datos_en_appdata", return_value=True):
                        portable = cfg.dir_datos_portable()
            self.assertIsNone(portable)
            self.assertFalse((Path(tmp) / "datos").exists())

    def test_sin_permiso_de_escritura_junto_al_exe_no_revienta(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContAll.exe"
            exe.touch()
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    with mock.patch.object(cfg, "_hay_datos_en_appdata", return_value=False):
                        with mock.patch.object(Path, "mkdir", side_effect=OSError("sin permiso")):
                            self.assertIsNone(cfg.dir_datos_portable())

    def test_usa_la_carpeta_datos_si_existe_junto_al_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()  # ver nota sobre nombres 8.3 más arriba
            exe = tmp / "ContAll.exe"
            exe.touch()
            (Path(tmp) / "datos").mkdir()
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    portable = cfg.dir_datos_portable()
            self.assertEqual(portable, Path(tmp) / "datos")

    def test_dir_datos_prioriza_contaflow_data_sobre_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContAll.exe"
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
            tmp = Path(tmp).resolve()  # ver nota sobre nombres 8.3 más arriba
            exe = tmp / "ContAll.exe"
            exe.touch()
            (Path(tmp) / "datos").mkdir()
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CONTAFLOW_DATA", None)
                with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                    with mock.patch.object(sys, "executable", str(exe)):
                        resultado = cfg.dir_datos()
            self.assertEqual(resultado, Path(tmp) / "datos")

    def test_instalacion_existente_sigue_en_appdata_si_no_crea_la_carpeta(self):
        """El caso que no debe romperse nunca: alguien que ya usa ContAll
        (datos en AppData) actualiza el .exe. Sin la carpeta `datos` de
        manera explícita, sigue exactamente igual que antes — nunca "pierde"
        sus datos por quedar apuntando a una carpeta portable vacía."""
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ContAll.exe"
            exe.touch()
            # Sin carpeta "datos" creada, pero con datos reales en AppData.
            with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                with mock.patch.object(sys, "executable", str(exe)):
                    with mock.patch.object(cfg, "_hay_datos_en_appdata", return_value=True):
                        self.assertIsNone(cfg.dir_datos_portable())


class TestNombreLegado(unittest.TestCase):
    """v1.1.0 renombró el programa de ContaFlow a ContAll: la carpeta de
    datos por defecto pasa de `.../ContaFlow` a `.../ContAll`. Quien ya lo
    tenía instalado no debe "perder" sus empresas y comprobantes sólo por
    el cambio de nombre — ver `dir_datos_legado()`."""

    def test_ninguna_carpeta_legado_si_no_hay_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(cfg, "_carpeta_appdata", return_value=Path(tmp) / "ContaFlow"):
                self.assertIsNone(cfg.dir_datos_legado())

    def test_detecta_la_carpeta_legado_si_tiene_base_de_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            legado = Path(tmp) / "ContaFlow"
            legado.mkdir()
            (legado / "contaflow.db").touch()
            with mock.patch.object(cfg, "_carpeta_appdata", return_value=legado):
                self.assertEqual(cfg.dir_datos_legado(), legado)

    def test_dir_datos_usa_legado_si_esta_congelado_y_sin_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            legado = Path(tmp) / "ContaFlow"
            legado.mkdir()
            (legado / "contaflow.db").touch()
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CONTAFLOW_DATA", None)
                with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                    with mock.patch.object(cfg, "dir_datos_portable", return_value=None):
                        with mock.patch.object(cfg, "dir_datos_legado", return_value=legado):
                            resultado = cfg.dir_datos()
            self.assertEqual(resultado, legado)

    def test_dir_datos_ignora_legado_en_desarrollo(self):
        """python run.py (sin congelar) no consulta el nombre viejo: usa
        directo la carpeta con el nombre nuevo, como cualquier dev."""
        with tempfile.TemporaryDirectory() as tmp:
            nuevo = Path(tmp) / "ContAll"
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CONTAFLOW_DATA", None)
                with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=False):
                    with mock.patch.object(cfg, "_carpeta_appdata", return_value=nuevo):
                        with mock.patch.object(
                            cfg, "dir_datos_legado",
                            side_effect=AssertionError("no debería llamarse en desarrollo"),
                        ):
                            resultado = cfg.dir_datos()
            self.assertEqual(resultado, nuevo)

    def test_contaflow_data_sigue_ganando_sobre_el_legado(self):
        with tempfile.TemporaryDirectory() as tmp:
            legado = Path(tmp) / "ContaFlow"
            legado.mkdir()
            (legado / "contaflow.db").touch()
            explicita = Path(tempfile.mkdtemp(prefix="contaflow-explicita-"))
            with mock.patch.dict(os.environ, {"CONTAFLOW_DATA": str(explicita)}):
                with mock.patch.object(cfg, "es_ejecutable_congelado", return_value=True):
                    with mock.patch.object(cfg, "dir_datos_legado", return_value=legado):
                        resultado = cfg.dir_datos()
            self.assertEqual(resultado, explicita)


if __name__ == "__main__":
    unittest.main(verbosity=2)
