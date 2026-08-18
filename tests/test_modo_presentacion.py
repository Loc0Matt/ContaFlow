"""Pruebas del modo presentación (bloqueo global de escritura)."""
from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-presentacion-"))
# Sin CONTAFLOW_DB_URL propio: que quede en el "contaflow.db" por defecto de
# esa carpeta, igual que RUTA_BD — si no, crear_respaldo() (usado por el
# respaldo automático de las migraciones) buscaría un archivo que nunca
# se creó, porque apuntarían a nombres distintos.

from contaflow.database import SessionLocal, crear_esquema  # noqa: E402
from contaflow.services import modo_presentacion as mp  # noqa: E402
from contaflow.services.seed import sembrar_globales  # noqa: E402
from contaflow.services.utils import digito_verificador  # noqa: E402


class TestServicio(unittest.TestCase):
    def setUp(self):
        crear_esquema()
        self.db = SessionLocal()
        sembrar_globales(self.db)
        # Estado limpio al empezar cada prueba, sin importar el orden.
        mp.desactivar(self.db)

    def tearDown(self):
        self.db.close()

    def test_arranca_desactivado(self):
        self.assertFalse(mp.esta_activo(self.db))

    def test_activar_y_desactivar(self):
        mp.activar(self.db)
        self.assertTrue(mp.esta_activo(self.db))
        mp.desactivar(self.db)
        self.assertFalse(mp.esta_activo(self.db))

    def test_alternar(self):
        self.assertFalse(mp.esta_activo(self.db))
        self.assertTrue(mp.alternar(self.db))
        self.assertTrue(mp.esta_activo(self.db))
        self.assertFalse(mp.alternar(self.db))
        self.assertFalse(mp.esta_activo(self.db))

    def test_es_un_solo_parametro_global_no_duplicado(self):
        from sqlalchemy import select

        from contaflow.models import Parametro

        mp.activar(self.db)
        mp.desactivar(self.db)
        mp.activar(self.db)
        filas = self.db.scalars(
            select(Parametro).where(Parametro.clave == mp.CLAVE)
        ).all()
        self.assertEqual(len(filas), 1)
        self.assertIsNone(filas[0].empresa_id)


class TestBloqueoHTTP(unittest.TestCase):
    """Con el modo activo, ningún POST que escriba datos debe pasar —
    salvo los explícitamente exceptuados (login, navegación, el propio
    interruptor)."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("httpx no está instalado")

        from contaflow.app import crear_app
        from contaflow.models import Empresa, RegimenTributario

        cls.cliente = TestClient(crear_app())
        r = cls.cliente.post("/login", data={"username": "admin", "password": "admin"})
        assert r.status_code in (200, 303)

        # Al menos una empresa, o exigir_empresa() interrumpe cualquier POST
        # con "sin_empresa.html" antes de que el bloqueo entre a jugar.
        with SessionLocal() as db:
            from sqlalchemy import select

            if db.scalar(select(Empresa)) is None:
                cuerpo = "76111333"
                db.add(Empresa(
                    rut=f"{cuerpo}-{digito_verificador(cuerpo)}",
                    razon_social="Empresa de Prueba — Modo Presentación",
                    regimen=RegimenTributario.ART14D3,
                ))
                db.commit()

    def setUp(self):
        with SessionLocal() as db:
            mp.desactivar(db)

    def tearDown(self):
        with SessionLocal() as db:
            mp.desactivar(db)

    def test_activar_bloquea_una_escritura_real(self):
        # Antes de activar: crear una entidad funciona con normalidad.
        r = self.cliente.post("/maestros/entidades/guardar", data={
            "rut": "76.543.210-3", "razon_social": "Antes de activar",
            "es_cliente": "on",
        }, follow_redirects=False)
        self.assertEqual(r.status_code, 303)

        # Activar el modo presentación.
        r = self.cliente.post("/modo-presentacion/alternar", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        with SessionLocal() as db:
            self.assertTrue(mp.esta_activo(db))

        # Ahora un intento de escritura se bloquea, sin llegar al handler.
        r = self.cliente.post("/maestros/entidades/guardar", data={
            "rut": "77.111.222-6", "razon_social": "Durante modo presentación",
            "es_cliente": "on",
        }, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        r2 = self.cliente.get("/maestros/entidades")
        self.assertNotIn("Durante modo presentación", r2.text)
        self.assertIn("Antes de activar", r2.text)  # la de antes sí quedó

        # Pero las lecturas (GET) siguen funcionando sin problema.
        r = self.cliente.get("/")
        self.assertEqual(r.status_code, 200)

    def test_el_interruptor_se_puede_apagar_estando_activo(self):
        """Si el propio /modo-presentacion/alternar se bloqueara a sí mismo,
        no habría forma de volver a modo edición sin tocar la base a mano."""
        self.cliente.post("/modo-presentacion/alternar", follow_redirects=False)
        with SessionLocal() as db:
            self.assertTrue(mp.esta_activo(db))

        r = self.cliente.post("/modo-presentacion/alternar", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        with SessionLocal() as db:
            self.assertFalse(mp.esta_activo(db))

    def test_seleccionar_empresa_y_periodo_siguen_funcionando_activo(self):
        """Cambiar de empresa/período es navegación, no escritura de negocio."""
        from sqlalchemy import select

        from contaflow.models import Empresa

        with SessionLocal() as db:
            mp.activar(db)
            empresa = db.scalar(select(Empresa))

        if empresa is None:
            self.skipTest("no hay empresa de prueba disponible en este punto")

        r = self.cliente.post(
            "/seleccionar-periodo", data={"anio": 2026, "mes": 3}, follow_redirects=False
        )
        self.assertEqual(r.status_code, 303)

    def test_login_sigue_funcionando_con_el_modo_activo(self):
        """Nadie debería quedar sin poder ni siquiera entrar al sistema."""
        with SessionLocal() as db:
            mp.activar(db)
        otro = _cliente_nuevo()
        r = otro.post("/login", data={"username": "admin", "password": "admin"},
                       follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/")


def _cliente_nuevo():
    """Cliente HTTP nuevo, sin las cookies de sesión de la clase de arriba."""
    from fastapi.testclient import TestClient

    from contaflow.app import app

    return TestClient(app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
