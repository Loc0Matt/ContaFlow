"""Pruebas del control de versión de esquema (contaflow.services.migraciones).

Usa sus propios motores SQLite temporales — no el `engine` global de
contaflow.database — para no interferir con el resto de la suite ni
depender del orden en que se ejecutan los demás archivos de prueba.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

from contaflow.services import migraciones as m


def _motor_vacio() -> "create_engine":
    """Motor SQLite temporal, sin ninguna tabla todavía."""
    tmp = Path(tempfile.mkdtemp(prefix="contaflow-mig-")) / "prueba.db"
    return create_engine(f"sqlite:///{tmp}", future=True)


def _motor_con_esquema() -> "create_engine":
    """Motor SQLite temporal con el esquema completo de hoy (como create_all)."""
    from contaflow import models  # noqa: F401  (registra los modelos)
    from contaflow.models.base import Base

    engine = _motor_vacio()
    Base.metadata.create_all(engine)
    return engine


class TestRegistro(unittest.TestCase):
    def test_el_registro_real_esta_ordenado_y_sin_duplicados(self):
        versiones = [x.version for x in m.MIGRACIONES]
        self.assertEqual(versiones, sorted(versiones))
        self.assertEqual(len(versiones), len(set(versiones)))

    def test_version_actual_es_la_maxima_del_registro(self):
        esperado = max((x.version for x in m.MIGRACIONES), default=0)
        self.assertEqual(m.VERSION_ACTUAL, esperado)

    def test_registro_desordenado_se_rechaza(self):
        malas = (
            m.Migracion(2, "b", lambda conn: None),
            m.Migracion(1, "a", lambda conn: None),
        )
        original = m.MIGRACIONES
        m.MIGRACIONES = malas
        try:
            with self.assertRaises(RuntimeError):
                m._validar_registro()
        finally:
            m.MIGRACIONES = original

    def test_registro_con_version_repetida_se_rechaza(self):
        malas = (
            m.Migracion(1, "a", lambda conn: None),
            m.Migracion(1, "a de nuevo", lambda conn: None),
        )
        original = m.MIGRACIONES
        m.MIGRACIONES = malas
        try:
            with self.assertRaises(RuntimeError):
                m._validar_registro()
        finally:
            m.MIGRACIONES = original


class TestHelpers(unittest.TestCase):
    def test_tabla_existe(self):
        engine = _motor_con_esquema()
        with engine.connect() as conn:
            self.assertTrue(m.tabla_existe(conn, "parametro"))
            self.assertFalse(m.tabla_existe(conn, "tabla_que_no_existe"))

    def test_columna_existe(self):
        engine = _motor_con_esquema()
        with engine.connect() as conn:
            self.assertTrue(m.columna_existe(conn, "parametro", "clave"))
            self.assertFalse(m.columna_existe(conn, "parametro", "columna_inventada"))
            self.assertFalse(m.columna_existe(conn, "tabla_que_no_existe", "clave"))

    def test_agregar_columna_si_falta_la_agrega(self):
        engine = _motor_con_esquema()
        with engine.begin() as conn:
            m.agregar_columna_si_falta(conn, "parametro", "columna_nueva", "TEXT DEFAULT ''")
        with engine.connect() as conn:
            self.assertTrue(m.columna_existe(conn, "parametro", "columna_nueva"))

    def test_agregar_columna_si_falta_es_idempotente(self):
        """Ejecutarla dos veces no debe reventar (create_all ya la pudo haber creado)."""
        engine = _motor_con_esquema()
        with engine.begin() as conn:
            m.agregar_columna_si_falta(conn, "parametro", "columna_nueva", "TEXT DEFAULT ''")
        with engine.begin() as conn:
            m.agregar_columna_si_falta(conn, "parametro", "columna_nueva", "TEXT DEFAULT ''")
        with engine.connect() as conn:
            self.assertTrue(m.columna_existe(conn, "parametro", "columna_nueva"))

    def test_quitar_columna_si_existe_la_quita(self):
        engine = _motor_con_esquema()
        with engine.begin() as conn:
            m.agregar_columna_si_falta(conn, "parametro", "vieja", "TEXT")
        with engine.connect() as conn:
            self.assertTrue(m.columna_existe(conn, "parametro", "vieja"))
        with engine.begin() as conn:
            m.quitar_columna_si_existe(conn, "parametro", "vieja")
        with engine.connect() as conn:
            self.assertFalse(m.columna_existe(conn, "parametro", "vieja"))

    def test_quitar_columna_si_existe_es_idempotente(self):
        """Sobre una base nueva, que nunca tuvo la columna, no debe reventar."""
        engine = _motor_con_esquema()
        with engine.begin() as conn:
            m.quitar_columna_si_existe(conn, "usuario", "rol")
        with engine.begin() as conn:
            m.quitar_columna_si_existe(conn, "usuario", "rol")  # segunda vez, sigue sin existir


class TestVersionGuardada(unittest.TestCase):
    def test_sin_tabla_parametro_devuelve_cero(self):
        engine = _motor_vacio()
        with engine.connect() as conn:
            self.assertEqual(m.version_guardada(conn), 0)

    def test_sin_fila_de_version_devuelve_cero(self):
        engine = _motor_con_esquema()
        with engine.connect() as conn:
            self.assertEqual(m.version_guardada(conn), 0)

    def test_escribir_y_leer_version(self):
        engine = _motor_con_esquema()
        with engine.begin() as conn:
            m._escribir_version(conn, 3)
        with engine.connect() as conn:
            self.assertEqual(m.version_guardada(conn), 3)
        # Volver a escribir actualiza la misma fila, no crea una segunda.
        with engine.begin() as conn:
            m._escribir_version(conn, 5)
        with engine.connect() as conn:
            self.assertEqual(m.version_guardada(conn), 5)
            filas = conn.execute(text(
                "SELECT COUNT(*) FROM parametro WHERE clave = :c"
            ), {"c": m.CLAVE_VERSION}).scalar()
            self.assertEqual(filas, 1)


class TestMigrarEsquema(unittest.TestCase):
    def test_sin_pendientes_no_hace_nada_ni_respalda(self):
        """Con el registro real vacío, una base al día no debe tocarse.

        Se aísla MIGRACIONES para que esto siga siendo cierto sin importar
        cuántas migraciones reales existan en un momento dado — el propio
        registro real ya se prueba aparte, aplicado, en los tests de abajo.
        """
        engine = _motor_con_esquema()
        llamadas = []
        original = m.MIGRACIONES
        m.MIGRACIONES = ()
        try:
            aplicadas = m.migrar_esquema(engine, respaldar=lambda: llamadas.append("respaldo"))
        finally:
            m.MIGRACIONES = original
        self.assertEqual(aplicadas, [])
        self.assertEqual(llamadas, [])

    def test_el_registro_real_aplicado_a_una_base_nueva_es_inofensivo(self):
        """El registro real, aplicado a una base recién creada (mismo esquema
        de hoy), va a tener migraciones "pendientes" por versión — una base
        nueva parte en la versión 0 — pero cada una debe ser un no-op, porque
        create_all() ya construyó el esquema actual. Se respalda igual (no
        hay forma barata de saber de antemano que no hacía falta), pero no
        debe reventar ni dejar la base en un estado raro."""
        engine = _motor_con_esquema()
        aplicadas = m.migrar_esquema(engine, respaldar=lambda: None)
        self.assertEqual(aplicadas, [x.version for x in m.MIGRACIONES])
        # Segunda pasada: ya no hay nada pendiente.
        self.assertEqual(m.migrar_esquema(engine, respaldar=lambda: None), [])

    def test_aplica_pendientes_en_orden_y_respalda_una_vez(self):
        engine = _motor_con_esquema()
        orden: list[int] = []
        llamadas = []

        falsas = (
            m.Migracion(1, "agrega columna x", lambda conn: (
                m.agregar_columna_si_falta(conn, "parametro", "col_x", "TEXT DEFAULT ''"),
                orden.append(1),
            )),
            m.Migracion(2, "agrega columna y", lambda conn: (
                m.agregar_columna_si_falta(conn, "parametro", "col_y", "TEXT DEFAULT ''"),
                orden.append(2),
            )),
        )
        original = m.MIGRACIONES
        m.MIGRACIONES = falsas
        try:
            aplicadas = m.migrar_esquema(engine, respaldar=lambda: llamadas.append("respaldo"))
        finally:
            m.MIGRACIONES = original

        self.assertEqual(aplicadas, [1, 2])
        self.assertEqual(orden, [1, 2])
        self.assertEqual(llamadas, ["respaldo"])
        with engine.connect() as conn:
            self.assertTrue(m.columna_existe(conn, "parametro", "col_x"))
            self.assertTrue(m.columna_existe(conn, "parametro", "col_y"))
            self.assertEqual(m.version_guardada(conn), 2)

    def test_segunda_pasada_no_reaplica_nada(self):
        engine = _motor_con_esquema()
        contador = {"n": 0}

        falsas = (m.Migracion(1, "agrega columna x", lambda conn: (
            m.agregar_columna_si_falta(conn, "parametro", "col_x", "TEXT DEFAULT ''"),
            contador.__setitem__("n", contador["n"] + 1),
        )),)
        original = m.MIGRACIONES
        m.MIGRACIONES = falsas
        try:
            m.migrar_esquema(engine, respaldar=lambda: None)
            aplicadas_2 = m.migrar_esquema(engine, respaldar=lambda: None)
        finally:
            m.MIGRACIONES = original

        self.assertEqual(contador["n"], 1)
        self.assertEqual(aplicadas_2, [])

    def test_un_error_de_respaldo_no_impide_migrar(self):
        """El respaldo automático es una red de seguridad, no un bloqueo:
        si falla (disco lleno, permisos, lo que sea) igual conviene dejar
        la base de datos al día en vez de arrancar con un esquema viejo."""
        engine = _motor_con_esquema()

        def respaldo_roto():
            raise OSError("disco lleno")

        falsas = (m.Migracion(1, "agrega columna x", lambda conn: m.agregar_columna_si_falta(
            conn, "parametro", "col_x", "TEXT DEFAULT ''")),)
        original = m.MIGRACIONES
        m.MIGRACIONES = falsas
        try:
            aplicadas = m.migrar_esquema(engine, respaldar=respaldo_roto)
        finally:
            m.MIGRACIONES = original

        self.assertEqual(aplicadas, [1])
        with engine.connect() as conn:
            self.assertTrue(m.columna_existe(conn, "parametro", "col_x"))


class TestIntegracionConCrearEsquema(unittest.TestCase):
    """crear_esquema() debe llamar a migrar_esquema() sola, sin que haga
    falta acordarse de invocarla aparte en cada punto de entrada."""

    def test_una_base_nueva_queda_al_dia(self):
        import contaflow.database as bd

        tmp = Path(tempfile.mkdtemp(prefix="contaflow-mig-integ-")) / "prueba.db"
        engine_original = bd.engine
        bd.engine = create_engine(f"sqlite:///{tmp}", future=True)
        try:
            bd.crear_esquema()
            with bd.engine.connect() as conn:
                self.assertEqual(m.version_guardada(conn), m.VERSION_ACTUAL)
        finally:
            bd.engine = engine_original


class TestMigracionDeUsuarioRol(unittest.TestCase):
    """Caso real: la Release v1.0.0, ya publicada, creó `usuario.rol` NOT NULL.
    Una instalación que actualice el .exe sin tocar sus datos debe seguir
    funcionando — sin esto, cualquier alta de usuario nuevo fallaría contra
    esa columna obsoleta."""

    def _base_como_v1_0_0(self):
        """Arma el esquema actual y le vuelve a agregar `rol` a mano, como
        si fuera una base creada con la versión publicada."""
        engine = _motor_con_esquema()
        with engine.begin() as conn:
            m.agregar_columna_si_falta(conn, "usuario", "rol", "VARCHAR(20) NOT NULL DEFAULT 'ADMIN'")
        return engine

    def test_migrar_quita_rol_y_el_usuario_sigue_operable(self):
        engine = self._base_como_v1_0_0()
        with engine.connect() as conn:
            self.assertTrue(m.columna_existe(conn, "usuario", "rol"))

        aplicadas = m.migrar_esquema(engine, respaldar=lambda: None)
        self.assertIn(1, aplicadas)

        with engine.connect() as conn:
            self.assertFalse(m.columna_existe(conn, "usuario", "rol"))

        # Insertar un usuario nuevo (como haría guardar_usuario) no debe
        # chocar con una columna NOT NULL que el ORM ya no conoce.
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO usuario (username, nombre, password_hash, activo) "
                "VALUES ('juan', 'Juan', 'hash', 1)"
            ))
        with engine.connect() as conn:
            fila = conn.execute(text("SELECT username FROM usuario WHERE username='juan'")).first()
        self.assertEqual(fila[0], "juan")


if __name__ == "__main__":
    unittest.main(verbosity=2)
