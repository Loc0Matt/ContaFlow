"""Control de versión del esquema de base de datos.

`Base.metadata.create_all()` (la llama `database.crear_esquema()`) sólo crea
las tablas que falten: nunca modifica una que ya existe. Si una versión
futura de ContaFlow agrega una columna a una tabla existente, hace falta un
paso explícito que la agregue también en las bases de datos ya instaladas
— si no, el programa fallaría al leer o escribir ese campo apenas alguien
reemplazara su ContaFlow.exe viejo por uno nuevo sin tocar sus datos.

Este módulo se encarga de eso solo, en cada arranque, sin que haga falta
acordarse en cada actualización:

- La versión de esquema aplicada queda guardada en la tabla `parametro`
  (clave "version_esquema", un parámetro global).
- `migrar_esquema()` corre siempre al final de `crear_esquema()`, compara
  esa versión contra el registro `MIGRACIONES` y aplica las que falten, en
  orden, cada una en su propia transacción.
- Si hay algo pendiente, antes de tocar la base de datos crea un respaldo
  completo. Si no hay nada pendiente (el caso normal, en casi todos los
  arranques) no toca nada ni pide respaldo.

Cómo agregar una migración nueva:

1. Escribe una función que reciba una `Connection` de SQLAlchemy y aplique
   el cambio con SQL directo — no con los modelos del ORM. Los modelos
   describen el esquema de HOY; usarlos para migrar una base de datos vieja
   mezclaría "cómo se ve la tabla ahora" con "qué le falta a esta base en
   particular", que son dos cosas distintas.
2. Hazla segura de ejecutar dos veces (comprueba si la columna ya existe
   antes de agregarla, por ejemplo). Es imprescindible: una base de datos
   nueva ya nace con el esquema actual gracias a `create_all()`, así que
   sus migraciones "viejas" se ejecutan igual, pero no deben romper nada
   al encontrar que ese cambio ya estaba de fábrica.
3. Agrégala al final de `MIGRACIONES` con el número de versión siguiente.
   Nunca edites, borres ni reordenes una entrada que ya se haya publicado:
   las instalaciones que ya la aplicaron y las que la aplicarán por primera
   vez deben terminar con el mismo resultado.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

log = logging.getLogger("contaflow")

#: Clave del parámetro global donde queda la versión de esquema aplicada.
CLAVE_VERSION = "version_esquema"


@dataclass(frozen=True)
class Migracion:
    version: int
    descripcion: str
    aplicar: Callable[[Connection], None]


def tabla_existe(conn: Connection, tabla: str) -> bool:
    return inspect(conn).has_table(tabla)


def columna_existe(conn: Connection, tabla: str, columna: str) -> bool:
    if not tabla_existe(conn, tabla):
        return False
    return columna in {c["name"] for c in inspect(conn).get_columns(tabla)}


def agregar_columna_si_falta(conn: Connection, tabla: str, columna: str, definicion_sql: str) -> None:
    """`ALTER TABLE ... ADD COLUMN`, sólo si la columna no existe todavía.

    SQLite permite agregar columnas de forma directa (a diferencia de
    quitarlas o renombrarlas, que piden versiones más nuevas de SQLite); es,
    con diferencia, el cambio de esquema más común en una app que va
    creciendo con el tiempo, así que es el único helper que se ofrece acá.
    Para lo poco frecuente — una tabla nueva relacionada, un cambio de tipo
    de dato — la migración escribe su propio SQL directamente.
    """
    if columna_existe(conn, tabla, columna):
        return
    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion_sql}"))


def quitar_columna_si_existe(conn: Connection, tabla: str, columna: str) -> None:
    """`ALTER TABLE ... DROP COLUMN`, sólo si la columna existe todavía.

    Requiere SQLite 3.35+ (2021); el intérprete embebido en el .exe siempre
    trae una versión más nueva, así que no hace falta contemplar el caso
    contrario. Si la columna no existe (base nueva, o ya migrada antes),
    no hace nada.
    """
    if not columna_existe(conn, tabla, columna):
        return
    conn.execute(text(f"ALTER TABLE {tabla} DROP COLUMN {columna}"))


# ---------------------------------------------------------------------------
# Registro de migraciones. Se agregan al final; nunca se edita una que ya
# haya salido a producción, o las instalaciones que ya la aplicaron y las
# que la van a aplicar por primera vez quedarían con historias distintas.
# ---------------------------------------------------------------------------
MIGRACIONES: tuple[Migracion, ...] = (
    Migracion(
        1, "Quita Usuario.rol (se elimina el sistema de roles)",
        lambda conn: quitar_columna_si_existe(conn, "usuario", "rol"),
    ),
)

VERSION_ACTUAL = max((m.version for m in MIGRACIONES), default=0)


def _validar_registro() -> None:
    versiones = [m.version for m in MIGRACIONES]
    if versiones != sorted(versiones) or len(versiones) != len(set(versiones)):
        raise RuntimeError(
            "MIGRACIONES debe tener versiones únicas y en orden ascendente "
            f"(agrega siempre al final); encontrado: {versiones}"
        )


_validar_registro()


def version_guardada(conn: Connection) -> int:
    """Versión de esquema aplicada según la base de datos. 0 si no hay ninguna."""
    if not tabla_existe(conn, "parametro"):
        return 0
    fila = conn.execute(text(
        "SELECT valor FROM parametro WHERE empresa_id IS NULL AND clave = :clave"
    ), {"clave": CLAVE_VERSION}).first()
    valor = fila[0] if fila else None
    return int(valor) if valor is not None and str(valor).isdigit() else 0


def _escribir_version(conn: Connection, version: int) -> None:
    existe = conn.execute(text(
        "SELECT 1 FROM parametro WHERE empresa_id IS NULL AND clave = :clave"
    ), {"clave": CLAVE_VERSION}).first()
    if existe:
        conn.execute(text(
            "UPDATE parametro SET valor = :v WHERE empresa_id IS NULL AND clave = :clave"
        ), {"v": str(version), "clave": CLAVE_VERSION})
    else:
        conn.execute(text(
            "INSERT INTO parametro (empresa_id, clave, valor, descripcion) "
            "VALUES (NULL, :clave, :v, :d)"
        ), {"clave": CLAVE_VERSION, "v": str(version),
            "d": "Versión del esquema de base de datos aplicada. No editar a mano."})


def migraciones_pendientes(conn: Connection) -> list[Migracion]:
    actual = version_guardada(conn)
    return [m for m in MIGRACIONES if m.version > actual]


def migrar_esquema(engine: Engine, *, respaldar: Callable[[], object] | None = None) -> list[int]:
    """Aplica las migraciones pendientes. Devuelve las versiones aplicadas.

    Si no hay ninguna pendiente no toca la base de datos ni intenta un
    respaldo: un arranque normal, con el esquema ya al día (el caso de
    prácticamente todos los arranques), queda intacto.
    """
    with engine.connect() as conn:
        pendientes = migraciones_pendientes(conn)
    if not pendientes:
        return []

    if respaldar is None:
        def respaldar():
            from contaflow.services.exportar import crear_respaldo
            return crear_respaldo()

    try:
        ruta = respaldar()
        log.info("Respaldo automático antes de migrar el esquema: %s", ruta)
    except Exception:
        log.exception("No se pudo crear el respaldo automático antes de migrar el esquema.")

    aplicadas: list[int] = []
    for migracion in pendientes:
        with engine.begin() as conn:
            # Se revisa otra vez dentro de la transacción: si algo más ya la
            # aplicó mientras se hacía el respaldo, no se repite.
            if migracion.version <= version_guardada(conn):
                continue
            log.info("Aplicando migración de esquema %s: %s", migracion.version, migracion.descripcion)
            migracion.aplicar(conn)
            _escribir_version(conn, migracion.version)
            aplicadas.append(migracion.version)
    return aplicadas
