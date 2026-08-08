"""Motor de base de datos y sesión de SQLAlchemy."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from contaflow.config import URL_BD

engine = create_engine(
    URL_BD,
    connect_args={"check_same_thread": False} if URL_BD.startswith("sqlite") else {},
    future=True,
)


@event.listens_for(engine, "connect")
def _configurar_sqlite(dbapi_connection, _record):  # pragma: no cover - infra
    """Activa claves foráneas y modo WAL (mejor concurrencia lectura/escritura)."""
    if not URL_BD.startswith("sqlite"):
        return
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: entrega una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def sesion() -> Iterator[Session]:
    """Sesión transaccional para scripts y tareas internas."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def crear_esquema() -> None:
    from contaflow import models  # noqa: F401  (registra los modelos)
    from contaflow.models.base import Base

    Base.metadata.create_all(engine)
