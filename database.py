import os
from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

# Si existe DATABASE_URL (la vamos a configurar en Render), usamos
# Postgres de verdad. Si no existe (como en tu máquina local, donde
# no hace falta configurarla), caemos a SQLite como hasta ahora — así
# puedes seguir desarrollando localmente sin depender de internet.
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Postgres NO necesita connect_args especiales como SQLite.
    engine = create_engine(DATABASE_URL, echo=True)
else:
    SQLITE_FILE_NAME = "database.db"
    SQLITE_URL = f"sqlite:///{SQLITE_FILE_NAME}"
    connect_args = {"check_same_thread": False}
    engine = create_engine(SQLITE_URL, echo=True, connect_args=connect_args)


def create_db_and_tables():
    """Crea las tablas si aún no existen — funciona igual sin importar
    si el engine de arriba apunta a SQLite o a Postgres. Esta es la
    gracia de usar SQLModel/SQLAlchemy: tu código de aquí en adelante
    no sabe (ni le importa) con qué motor de base de datos está hablando.
    """
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency que abre una sesión de base de datos por cada
    petición y la cierra al terminar."""
    with Session(engine) as session:
        yield session