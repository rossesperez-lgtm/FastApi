# ============================================================
# migrations/env.py — Configuración de Alembic para este proyecto
# ============================================================
# Alembic ejecuta este archivo cada vez que corres un comando
# (alembic revision, alembic upgrade, etc.). Le dice dos cosas:
#   1. A QUÉ base de datos conectarse (misma lógica que database.py).
#   2. CÓMO debería ser el esquema (tus modelos User e Item), para
#      poder compararlo con la base real y detectar diferencias.

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Este import es imprescindible aunque no se use directamente: al
# importar las clases con table=True, SQLModel las registra en
# SQLModel.metadata. Sin él, Alembic vería un esquema vacío y
# "autogenerate" no detectaría ninguna tabla.
# Efecto secundario: esto carga todo jwt_auth_users_SQLModel.py, por
# eso Alembic también necesita SECRET_KEY disponible en tu .env.
from routers.jwt_auth_users_SQLModel import User, Item  # noqa: F401

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# El "esquema deseado": todas las tablas definidas en tus modelos.
target_metadata = SQLModel.metadata

# Misma lógica que database.py: si existe DATABASE_URL usamos Postgres;
# si no, SQLite local. Así la URL real nunca queda escrita en
# alembic.ini (que SÍ se sube a git) — solo vive en variables de entorno.
DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///database.db"

# alembic.ini usa el símbolo % para interpolar valores, así que si la
# URL trae un % (por ejemplo en una contraseña) hay que duplicarlo.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Modo 'offline': no se conecta a la base, solo genera el SQL."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo normal: se conecta a la base y aplica las migraciones."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite no soporta muchos ALTER TABLE (por ejemplo borrar o
            # cambiar una columna). "Batch mode" lo resuelve recreando la
            # tabla por debajo. Postgres no lo necesita.
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
