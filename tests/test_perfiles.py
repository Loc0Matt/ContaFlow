"""Pruebas del asistente de perfil inicial (contaflow/services/perfiles.py)."""
from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-perfiles-"))

from contaflow.database import SessionLocal  # noqa: E402
from contaflow.services import perfiles as pf  # noqa: E402


class TestModuloPerfiles(unittest.TestCase):
    """La mayoría de estas pruebas son sobre funciones puras (visible(),
    tope_empresas()) que no tocan la base de datos — cada una de las que sí
    la toca deja su propio estado explícito, sin depender de un setUp
    compartido."""

    def test_sin_elegir_todo_es_visible(self):
        self.assertTrue(pf.visible("formulario_22", None))
        self.assertTrue(pf.visible("centros_costo", None))

    def test_seccion_no_listada_siempre_visible(self):
        for perfil in pf.PERFILES:
            self.assertTrue(pf.visible("panel", perfil))
            self.assertTrue(pf.visible("cualquier_cosa_inventada", perfil))

    def test_emprendedor_oculta_lo_avanzado(self):
        for seccion in pf.SECCIONES:
            self.assertFalse(pf.visible(seccion, "emprendedor"))

    def test_contador_no_oculta_nada(self):
        for seccion in pf.SECCIONES:
            self.assertTrue(pf.visible(seccion, "contador"))

    def test_pyme_intermedio(self):
        # Balance 8 columnas y centros de costo siguen ocultos para pyme.
        self.assertFalse(pf.visible("balance_8_columnas", "pyme"))
        self.assertFalse(pf.visible("centros_costo", "pyme"))
        # El resto ya se muestra.
        self.assertTrue(pf.visible("formulario_22", "pyme"))
        self.assertTrue(pf.visible("activo_fijo", "pyme"))

    def test_tope_empresas(self):
        self.assertEqual(pf.tope_empresas("emprendedor"), 1)
        self.assertEqual(pf.tope_empresas("pyme"), 1)
        self.assertIsNone(pf.tope_empresas("contador"))
        self.assertIsNone(pf.tope_empresas(None))

    def test_elegir_perfil_invalido_lanza(self):
        with SessionLocal() as db:
            with self.assertRaises(ValueError):
                pf.elegir_perfil(db, "no-existe")

    def test_perfil_actual_sin_elegir_es_none(self):
        with SessionLocal() as db:
            from sqlalchemy import delete

            from contaflow.models import Parametro

            db.execute(delete(Parametro).where(Parametro.clave == pf.CLAVE))
            db.commit()
            self.assertIsNone(pf.perfil_actual(db))

    def test_elegir_y_leer(self):
        with SessionLocal() as db:
            pf.elegir_perfil(db, "pyme")
            self.assertEqual(pf.perfil_actual(db), "pyme")
            pf.elegir_perfil(db, "contador")  # se puede cambiar después
            self.assertEqual(pf.perfil_actual(db), "contador")

    def test_es_una_sola_fila_no_duplicada(self):
        from sqlalchemy import select

        from contaflow.models import Parametro

        with SessionLocal() as db:
            pf.elegir_perfil(db, "emprendedor")
            pf.elegir_perfil(db, "pyme")
            pf.elegir_perfil(db, "contador")
            filas = db.scalars(select(Parametro).where(Parametro.clave == pf.CLAVE)).all()
        self.assertEqual(len(filas), 1)


class TestFlujoHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("httpx no está instalado")
        cls.TestClient = TestClient

    def setUp(self):
        from sqlalchemy import delete, select

        from contaflow.app import crear_app
        from contaflow.models import Empresa, Parametro, Usuario
        from contaflow.services import modo_presentacion
        from contaflow.services.seguridad import hash_password

        self.cliente = self.TestClient(crear_app())
        # Estado conocido, sin importar qué haya dejado otra clase/archivo
        # que comparta esta misma base de datos (ver notas largas en
        # test_seguridad_login.py y test_modo_presentacion.py sobre esto).
        # Se incluyen las empresas: varias pruebas de esta clase crean
        # alguna con un RUT fijo, y sin limpiar antes chocarían por
        # duplicado con lo que haya dejado una prueba anterior de esta
        # misma clase (que sí corren sobre la misma base, en orden
        # alfabético, no el de definición).
        with SessionLocal() as db:
            modo_presentacion.desactivar(db)
            db.execute(delete(Parametro).where(Parametro.clave == pf.CLAVE))
            db.execute(delete(Empresa))
            db.commit()
            admin = db.scalar(select(Usuario).where(Usuario.username == "admin"))
            if admin is not None:
                admin.password_hash = hash_password("admin")
                admin.debe_cambiar_password = False
                admin.intentos_fallidos = 0
                admin.bloqueado_hasta = None
                db.commit()
        self.cliente.post("/login", data={"username": "admin", "password": "admin"},
                          follow_redirects=False)

    def test_sin_perfil_elegido_redirige_a_bienvenida(self):
        r = self.cliente.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/bienvenida")

        # Y la propia pantalla del asistente sí debe cargar.
        r = self.cliente.get("/bienvenida")
        self.assertEqual(r.status_code, 200)
        self.assertIn("perfil", r.text.lower())

    def test_perfil_invalido_se_rechaza(self):
        r = self.cliente.post("/bienvenida", data={"perfil": "invalido"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/bienvenida")
        with SessionLocal() as db:
            self.assertIsNone(pf.perfil_actual(db))

    def test_elegir_perfil_por_primera_vez_lleva_a_crear_empresa(self):
        r = self.cliente.post("/bienvenida", data={"perfil": "pyme"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/empresas/nueva")
        with SessionLocal() as db:
            self.assertEqual(pf.perfil_actual(db), "pyme")

        # Ya elegido, la navegación normal deja de rebotar a /bienvenida.
        r = self.cliente.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 200)

    def test_cambiar_perfil_despues_no_redirige_a_crear_empresa(self):
        self.cliente.post("/bienvenida", data={"perfil": "emprendedor"}, follow_redirects=False)
        r = self.cliente.post("/bienvenida", data={"perfil": "contador"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/")

    def test_sidebar_oculta_secciones_para_emprendedor(self):
        self.cliente.post("/bienvenida", data={"perfil": "emprendedor"}, follow_redirects=False)
        html = self.cliente.get("/").text
        self.assertNotIn("Formulario 22", html)
        self.assertNotIn("Balance 8 columnas", html)
        self.assertNotIn("Centros de costo", html)
        # El núcleo sigue ahí.
        self.assertIn("Ventas</a>", html)
        self.assertIn("Formulario 29", html)

    def test_sidebar_completo_para_contador(self):
        self.cliente.post("/bienvenida", data={"perfil": "contador"}, follow_redirects=False)
        html = self.cliente.get("/").text
        self.assertIn("Formulario 22", html)
        self.assertIn("Balance 8 columnas", html)
        self.assertIn("Centros de costo", html)

    def test_tope_de_una_empresa_para_emprendedor(self):
        self.cliente.post("/bienvenida", data={"perfil": "emprendedor"}, follow_redirects=False)

        primera = self.cliente.post("/empresas/guardar", data={
            "rut": "76222333-3", "razon_social": "Mi Negocio EIRL", "regimen": "ART14D3",
        }, follow_redirects=False)
        self.assertEqual(primera.status_code, 303)
        self.assertEqual(primera.headers["location"], "/empresas")

        segunda = self.cliente.post("/empresas/guardar", data={
            "rut": "76333444-9", "razon_social": "Segundo Negocio SpA", "regimen": "ART14D3",
        }, follow_redirects=True)
        self.assertIn("sólo permite 1 empresa", segunda.text)

        from sqlalchemy import func, select

        from contaflow.models import Empresa

        with SessionLocal() as db:
            cantidad = db.scalar(select(func.count()).select_from(Empresa).where(Empresa.activa.is_(True)))
        self.assertEqual(cantidad, 1)

    def test_contador_sin_tope_de_empresas(self):
        self.cliente.post("/bienvenida", data={"perfil": "contador"}, follow_redirects=False)
        for i, rut in enumerate(["76222333-3", "76333444-9", "76444555-4"]):
            r = self.cliente.post("/empresas/guardar", data={
                "rut": rut, "razon_social": f"Cliente {i}", "regimen": "ART14D3",
            }, follow_redirects=False)
            self.assertEqual(r.status_code, 303, f"empresa {i} debería haberse creado")

    def test_editar_empresa_existente_no_choca_con_el_tope(self):
        """Editar (no crear) no debe contar contra el tope de 1 empresa."""
        self.cliente.post("/bienvenida", data={"perfil": "emprendedor"}, follow_redirects=False)
        self.cliente.post("/empresas/guardar", data={
            "rut": "76222333-3", "razon_social": "Mi Negocio EIRL", "regimen": "ART14D3",
        }, follow_redirects=False)

        from sqlalchemy import select

        from contaflow.models import Empresa

        with SessionLocal() as db:
            empresa = db.scalar(select(Empresa).where(Empresa.razon_social == "Mi Negocio EIRL"))
        self.assertIsNotNone(empresa, "la empresa creada arriba debería existir")

        r = self.cliente.post("/empresas/guardar", data={
            "empresa_id": empresa.id, "rut": empresa.rut, "razon_social": "Mi Negocio EIRL (editado)",
            "regimen": "ART14D3",
        }, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/empresas")


if __name__ == "__main__":
    unittest.main(verbosity=2)
