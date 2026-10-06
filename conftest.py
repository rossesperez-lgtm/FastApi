# ============================================================
# conftest.py — Fixtures compartidas por TODOS los tests
# ============================================================
# ⚠️ IMPORTANTE: este archivo va en la RAÍZ de tu proyecto (al mismo
# nivel que main.py), NO dentro de la carpeta tests/. Es justamente
# su ubicación la que hace posible que pytest encuentre tu proyecto
# y puedas escribir `from main import app` en los archivos de test.
#
# Un "fixture" en pytest es una función que prepara algo que tus
# tests necesitan (una conexión, un cliente HTTP, datos de prueba) y,
# opcionalmente, lo limpia después. Cualquier test que quiera usar un
# fixture solo necesita pedirlo como parámetro — pytest se encarga de
# ejecutarlo y pasarle el resultado automáticamente. Nunca lo llamas
# vos mismo con ().

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from main import app
from database import get_session

# Este import, aunque no se use directamente, es necesario: hace que
# Python registre las clases User e Item en SQLModel.metadata antes
# de que creemos las tablas de prueba. Sin importarlas, SQLModel no
# sabría que esas tablas existen.
from routers.jwt_auth_users_SQLModel import User, Item  # noqa: F401


@pytest.fixture(name="session")
def session_fixture():
    """Crea una base de datos SQLite EN MEMORIA, nueva y vacía, para
    cada test que la use.

    "sqlite://" (sin nombre de archivo después) le dice a SQLite que
    no use ningún archivo en disco — todo vive en RAM y desaparece
    apenas termina el test.

    StaticPool es necesario específicamente para bases en memoria:
    sin esto, SQLAlchemy podría abrir una conexión nueva en cada
    operación, y cada conexión nueva a una base ":memory:" es una
    base VACÍA distinta (no se comparten entre sí). StaticPool fuerza
    a que se reutilice siempre la misma conexión única, para que
    todo el test vea la misma base de datos.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)  # crea las tablas (users, items)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Da un TestClient listo para usar, configurado para que CUALQUIER
    endpoint que dependa de get_session reciba la sesión de prueba
    (en memoria) en vez de la sesión real.

    client.get(...), client.post(...), etc. funcionan exactamente
    igual que si fueran peticiones HTTP reales a tu API — pero todo
    ocurre en el mismo proceso, sin levantar un servidor de verdad,
    así que los tests corren mucho más rápido.
    """

    def get_session_override():
        return session

    # dependency_overrides es un diccionario: la CLAVE es la función
    # original (get_session, tal cual se usa en tus Depends(...)), y
    # el VALOR es la función que queremos usar en su lugar durante
    # los tests. FastAPI revisa este diccionario antes de resolver
    # cualquier dependencia.
    app.dependency_overrides[get_session] = get_session_override

    client = TestClient(app)
    yield client

    # Limpiamos el override al terminar, para no afectar a otros
    # tests que pudieran correr después y esperar el comportamiento
    # normal.
    app.dependency_overrides.clear()