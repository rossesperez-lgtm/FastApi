# ============================================================
# database.py — Configuración de la conexión a la base de datos
# ============================================================
# Este archivo tiene UNA sola responsabilidad: decirle a SQLModel
# cómo conectarse a la base de datos y cómo crear/entregar sesiones.
# Por eso es tan corto — no debería tener lógica de negocio aquí.

from sqlmodel import Session, SQLModel, create_engine

# Nombre del archivo físico donde SQLite va a guardar tus datos.
# SQLite guarda TODA la base de datos en un solo archivo (a diferencia
# de PostgreSQL o MySQL, que corren como un servidor aparte). Por eso
# para "tener una base de datos" acá, basta con este nombre de archivo.
SQLITE_FILE_NAME = "database.db"

# SQLAlchemy/SQLModel usan una "URL de conexión" para saber qué motor
# de base de datos usar. El prefijo "sqlite:///" le dice "usa el
# dialecto SQLite, y el archivo está en esta ruta". Si en el futuro
# cambias a PostgreSQL, esta URL cambiaría a algo como
# "postgresql://usuario:clave@localhost/mi_basededatos" — y el resto
# de tu código (los routers, los endpoints) NO tendría que cambiar,
# porque SQLModel abstrae esas diferencias.
SQLITE_URL = f"sqlite:///{SQLITE_FILE_NAME}"

# SQLite, a diferencia de otras bases de datos, por defecto no permite
# que la misma conexión se use desde threads (hilos) distintos — y
# FastAPI, al ser asíncrono, puede manejar peticiones en threads
# distintos. 'check_same_thread: False' le dice a SQLite "relájate,
# confía en que nosotros manejamos bien la concurrencia" (lo cual es
# cierto porque abrimos una sesión nueva por cada petición, ver abajo).
connect_args = {"check_same_thread": False}

# El 'engine' es el objeto central de SQLAlchemy/SQLModel: representa
# la conexión real a la base de datos y sabe cómo traducir tus
# consultas de Python a SQL. Se crea UNA sola vez cuando arranca la
# aplicación (no uno por petición).
#
# echo=True es muy útil mientras aprendes: hace que SQLModel imprima
# en la consola el SQL real que está ejecutando por cada operación.
# Si alguna vez quieres entender exactamente qué INSERT o SELECT se
# generó a partir de tu código Python, mira la consola de uvicorn.
# (En producción normalmente se pone echo=False para no llenar los
# logs de ruido.)
engine = create_engine(SQLITE_URL, echo=True, connect_args=connect_args)


def create_db_and_tables():
    """Crea las tablas en la base de datos si aún no existen.

    SQLModel.metadata es un registro interno que va guardando TODAS
    las clases que definiste con `table=True` en cualquier parte de
    tu proyecto (User, Item, etc.) — no hace falta que tú le digas
    "aquí están mis tablas", SQLModel ya las fue anotando apenas las
    importaste. .create_all(engine) revisa cuáles de esas tablas no
    existen todavía en el archivo database.db y las crea.

    Esta función se llama una sola vez, al arrancar la app (ver el
    'lifespan' en main.py). Si la tabla ya existe, no hace nada —
    por eso es seguro reiniciar el servidor sin perder tus datos.
    """
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency que abre una sesión de base de datos por cada
    petición y la cierra al terminar.

    Esto es una 'dependency' de FastAPI (las vas a ver en TODOS tus
    endpoints como `session: Session = Depends(get_session)`).

    El patrón `with Session(engine) as session: yield session` es
    clave para entender: en vez de un simple `return`, usamos
    `yield`. Esto convierte a get_session en un "generador", y le
    permite a FastAPI ejecutar código ANTES de la petición (abrir la
    sesión) y DESPUÉS de que termine (cerrarla automáticamente, por
    el `with`), incluso si el endpoint lanzó una excepción en el
    medio. Es la forma correcta de manejar recursos que hay que
    "abrir y después sí o sí cerrar" (conexiones, archivos, etc.)
    en FastAPI.

    Como se crea una sesión NUEVA por cada petición (no se reutiliza
    una sola para toda la app), cada request queda aislado del resto
    — por eso no hay problema de concurrencia entre peticiones
    simultáneas, aunque compartan el mismo 'engine'.
    """
    with Session(engine) as session:
        yield session
