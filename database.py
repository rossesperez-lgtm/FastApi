from sqlmodel import Session, SQLModel, create_engine

# Nombre del archivo de base de datos local que se creará automáticamente
SQLITE_FILE_NAME = "database.db"
SQLITE_URL = f"sqlite:///{SQLITE_FILE_NAME}"

# El argumento connect_args es específico de SQLite para permitir multihilos
connect_args = {"check_same_thread": False}
engine = create_engine(SQLITE_URL, echo=True, connect_args=connect_args)


def create_db_and_tables():
    """Crea las tablas en la base de datos si aún no existen."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency que abre una sesión de base de datos por cada petición y la cierra al terminar."""
    with Session(engine) as session:
        yield session
        