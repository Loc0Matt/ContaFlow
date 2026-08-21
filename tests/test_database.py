"""Pruebas de la configuración del motor SQLite (contaflow.database).

Usa su propio motor temporal — no el `engine` global — para no interferir
con el resto de la suite, pero conecta los mismos listeners reales del
módulo para probar el código de producción tal cual.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import Column, Integer, String, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from contaflow import database as db

Base = declarative_base()


class Contador(Base):
    __tablename__ = "contador"
    id = Column(Integer, primary_key=True)
    valor = Column(String, nullable=False)


def _motor_como_produccion():
    """Motor SQLite temporal con exactamente los mismos listeners que usa
    la aplicación real (connect_args, WAL, y los dos event listeners de
    contaflow.database) — no una reimplementación aparte."""
    tmp = Path(tempfile.mkdtemp(prefix="contaflow-db-")) / "prueba.db"
    engine = create_engine(
        f"sqlite:///{tmp}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    # Se enganchan las mismas funciones que usa el motor global de
    # contaflow.database, no copias — así la prueba cubre el código real.
    event.listen(engine, "connect", db._configurar_sqlite)
    event.listen(engine, "begin", db._iniciar_transaccion)
    Base.metadata.create_all(engine)
    return engine


class TestLecturaConsistenteEntreConexiones(unittest.TestCase):
    """Antes del fix, pysqlite no emite BEGIN antes de un SELECT: en modo
    WAL, una conexión reciclada del pool podía quedar leyendo una foto
    vieja de la base aunque otra conexión ya hubiera confirmado un cambio.
    Se manifestaba como fallos intermitentes justo después de guardar algo
    (ej: iniciar sesión fallaba justo después de cambiar la contraseña, y
    funcionaba al reintentar)."""

    def test_una_sesion_nueva_siempre_ve_el_ultimo_valor_escrito(self):
        engine = _motor_como_produccion()
        Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

        with Sesion() as s:
            s.add(Contador(id=1, valor="inicial"))
            s.commit()

        # Simula muchas peticiones HTTP sucesivas (cada una abre y cierra su
        # propia sesión, como hace get_db()) alternando escritura y lectura
        # por varias conexiones del pool — la falla original era exactamente
        # una de cada dos.
        for i in range(20):
            nuevo_valor = f"version-{i}"
            with Sesion() as escritor:
                fila = escritor.get(Contador, 1)
                fila.valor = nuevo_valor
                escritor.commit()

            with Sesion() as lector:
                fila = lector.get(Contador, 1)
                self.assertEqual(
                    fila.valor, nuevo_valor,
                    f"la sesión #{i} leyó un valor viejo tras un commit reciente "
                    "(lectura obsoleta entre conexiones del pool en modo WAL)",
                )

    def test_lecturas_puras_sucesivas_tambien_ven_una_escritura_intercalada(self):
        """Reproduce el caso exacto del login: N sesiones que sólo leen,
        con una escritura intercalada en medio — ninguna debe quedarse con
        la foto vieja."""
        engine = _motor_como_produccion()
        Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

        with Sesion() as s:
            s.add(Contador(id=1, valor="antes"))
            s.commit()

        # "Calienta" el pool con varias sesiones de sólo lectura, como las
        # que ocurren antes de cualquier cambio real (páginas de login, etc).
        for _ in range(5):
            with Sesion() as s:
                s.get(Contador, 1)

        with Sesion() as escritor:
            fila = escritor.get(Contador, 1)
            fila.valor = "despues"
            escritor.commit()

        for i in range(10):
            with Sesion() as lector:
                fila = lector.get(Contador, 1)
                self.assertEqual(
                    fila.valor, "despues",
                    f"la lectura #{i} tras el cambio todavía ve el valor viejo",
                )


if __name__ == "__main__":
    unittest.main()
