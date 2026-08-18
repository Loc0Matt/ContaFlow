"""Pruebas de P1-4: cambio de contraseña obligatorio + límite de intentos."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-login-"))

from contaflow.database import SessionLocal  # noqa: E402
from contaflow.services import seguridad as sg  # noqa: E402


class TestHelpersDeSeguridad(unittest.TestCase):
    def test_cuenta_bloqueada_sin_fecha(self):
        self.assertFalse(sg.cuenta_bloqueada(None))

    def test_cuenta_bloqueada_con_fecha_futura(self):
        futuro = datetime.now() + timedelta(minutes=5)
        self.assertTrue(sg.cuenta_bloqueada(futuro))

    def test_cuenta_bloqueada_con_fecha_pasada(self):
        pasado = datetime.now() - timedelta(minutes=5)
        self.assertFalse(sg.cuenta_bloqueada(pasado))

    def test_registrar_intento_fallido_no_bloquea_antes_del_maximo(self):
        intentos, hasta = sg.registrar_intento_fallido(0)
        self.assertEqual(intentos, 1)
        self.assertIsNone(hasta)

    def test_registrar_intento_fallido_bloquea_al_llegar_al_maximo(self):
        ahora = datetime(2026, 1, 1, 12, 0, 0)
        intentos, hasta = sg.registrar_intento_fallido(sg.MAX_INTENTOS_LOGIN - 1, ahora=ahora)
        self.assertEqual(intentos, sg.MAX_INTENTOS_LOGIN)
        self.assertEqual(hasta, ahora + timedelta(minutes=sg.BLOQUEO_MINUTOS))

    def test_validar_password_corta(self):
        self.assertIsNotNone(sg.validar_password("corta"))

    def test_validar_password_ok(self):
        self.assertIsNone(sg.validar_password("una-contraseña-larga"))


class TestFlujoHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("httpx no está instalado")
        cls.TestClient = TestClient

    def setUp(self):
        from sqlalchemy import select

        from contaflow.app import crear_app
        from contaflow.models import Usuario
        from contaflow.services.seguridad import hash_password

        self.cliente = self.TestClient(crear_app())
        # Los métodos de esta clase comparten la misma base en disco (igual
        # que TestAplicacionWeb en test_contaflow.py), y unittest no respeta
        # el orden de definición (corre alfabético): una prueba que cambia
        # la contraseña puede ejecutarse antes que otra que asume "admin".
        # Se deja el admin en un estado conocido al empezar cada prueba, sin
        # importar qué haya dejado la anterior ni en qué orden corran.
        from contaflow.services import modo_presentacion, perfiles

        with SessionLocal() as db:
            # Idem con el modo presentación y el perfil de instalación: son
            # flags globales compartidos, y otra clase (de este archivo o de
            # otro) puede haberlos dejado en un estado que estas pruebas no
            # esperan. "contador" para que, una vez cambiada la contraseña,
            # no aparezca de sorpresa el asistente de perfil bloqueando la
            # navegación que las pruebas dan por libre.
            modo_presentacion.desactivar(db)
            perfiles.elegir_perfil(db, "contador")
            admin = db.scalar(select(Usuario).where(Usuario.username == "admin"))
            if admin is not None:
                admin.password_hash = hash_password("admin")
                admin.debe_cambiar_password = True
                admin.intentos_fallidos = 0
                admin.bloqueado_hasta = None
                db.commit()

    def test_admin_recien_sembrado_debe_cambiar_password(self):
        from sqlalchemy import select

        from contaflow.models import Usuario

        with SessionLocal() as db:
            admin = db.scalar(select(Usuario).where(Usuario.username == "admin"))
            self.assertTrue(admin.debe_cambiar_password)

    def test_login_redirige_a_cambiar_password_mientras_no_se_cambie(self):
        self.cliente.post("/login", data={"username": "admin", "password": "admin"},
                          follow_redirects=False)
        r = self.cliente.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/configuracion/respaldos")

        # La propia pantalla de cambio de contraseña sí debe ser alcanzable.
        r = self.cliente.get("/configuracion/respaldos")
        self.assertEqual(r.status_code, 200)
        self.assertIn("cambia tu contraseña", r.text.lower())

    def test_cambiar_password_libera_el_bloqueo(self):
        self.cliente.post("/login", data={"username": "admin", "password": "admin"},
                          follow_redirects=False)
        r = self.cliente.post("/configuracion/cambiar-password", data={
            "password_actual": "admin", "password_nueva": "una-clave-bien-larga",
        }, follow_redirects=False)
        self.assertEqual(r.status_code, 303)

        # Ahora la navegación normal ya no rebota a /configuracion/respaldos.
        r = self.cliente.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 200)

        from sqlalchemy import select

        from contaflow.models import Usuario

        with SessionLocal() as db:
            admin = db.scalar(select(Usuario).where(Usuario.username == "admin"))
            self.assertFalse(admin.debe_cambiar_password)

    def test_password_nueva_muy_corta_se_rechaza(self):
        self.cliente.post("/login", data={"username": "admin", "password": "admin"},
                          follow_redirects=False)
        r = self.cliente.post("/configuracion/cambiar-password", data={
            "password_actual": "admin", "password_nueva": "corta",
        }, follow_redirects=True)
        self.assertIn("al menos 8 caracteres", r.text)

        from sqlalchemy import select

        from contaflow.models import Usuario

        with SessionLocal() as db:
            admin = db.scalar(select(Usuario).where(Usuario.username == "admin"))
            self.assertTrue(admin.debe_cambiar_password)  # sigue pendiente

    def test_bloqueo_tras_intentos_fallidos(self):
        for _ in range(sg.MAX_INTENTOS_LOGIN):
            self.cliente.post("/login", data={"username": "admin", "password": "mala"})

        # Aunque ahora se use la contraseña correcta, la cuenta ya está bloqueada.
        r = self.cliente.post("/login", data={"username": "admin", "password": "admin"})
        self.assertIn("Demasiados intentos", r.text)

        from sqlalchemy import select

        from contaflow.models import Usuario

        with SessionLocal() as db:
            admin = db.scalar(select(Usuario).where(Usuario.username == "admin"))
            self.assertIsNotNone(admin.bloqueado_hasta)
            self.assertTrue(sg.cuenta_bloqueada(admin.bloqueado_hasta))

    def test_login_correcto_resetea_los_intentos(self):
        self.cliente.post("/login", data={"username": "admin", "password": "mala"})
        self.cliente.post("/login", data={"username": "admin", "password": "mala"})
        self.cliente.post("/login", data={"username": "admin", "password": "admin"},
                          follow_redirects=False)

        from sqlalchemy import select

        from contaflow.models import Usuario

        with SessionLocal() as db:
            admin = db.scalar(select(Usuario).where(Usuario.username == "admin"))
            self.assertEqual(admin.intentos_fallidos, 0)
            self.assertIsNone(admin.bloqueado_hasta)


class TestMigracionUsuarioExistente(unittest.TestCase):
    """La migración #2 sólo debe forzar el cambio a quien todavía tiene la
    contraseña por defecto — no a quien ya la cambió antes de actualizar."""

    def test_marca_solo_a_quien_sigue_con_admin(self):
        from pathlib import Path

        from sqlalchemy import create_engine, text

        from contaflow import models  # noqa: F401
        from contaflow.models.base import Base
        from contaflow.services import migraciones as m
        from contaflow.services.seguridad import hash_password

        tmp = Path(tempfile.mkdtemp(prefix="contaflow-mig-login-")) / "prueba.db"
        engine = create_engine(f"sqlite:///{tmp}", future=True)
        Base.metadata.create_all(engine)

        # Simula el esquema de v1.0.0: sin las columnas nuevas todavía (las
        # quita, en vez de asumir que create_all() ya construyó el de hoy —
        # que sí las trae, con NOT NULL y sin default a nivel de SQL).
        with engine.begin() as conn:
            for columna in ("debe_cambiar_password", "intentos_fallidos", "bloqueado_hasta"):
                m.quitar_columna_si_existe(conn, "usuario", columna)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO usuario (username, nombre, password_hash, activo) "
                "VALUES ('admin', 'Administrador', :h, 1)"
            ), {"h": hash_password("admin")})
            conn.execute(text(
                "INSERT INTO usuario (username, nombre, password_hash, activo) "
                "VALUES ('juan', 'Juan', :h, 1)"
            ), {"h": hash_password("una-clave-distinta")})

        m.migrar_esquema(engine, respaldar=lambda: None)

        with engine.connect() as conn:
            filas = dict(conn.execute(
                text("SELECT username, debe_cambiar_password FROM usuario")
            ).all())
        self.assertEqual(filas["admin"], 1)
        self.assertEqual(filas["juan"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
