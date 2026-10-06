# ============================================================
# jwt_auth_users_SQLModel.py — Autenticación JWT + CRUD de
# usuarios e ítems, con base de datos SQLite real (vía SQLModel)
# ============================================================
# Este es el archivo más grande del proyecto, así que antes de leer
# el código línea por línea, conviene tener clara la foto completa:
#
#   1. MODELOS (clases con table=True): representan tablas reales
#      en la base de datos — User e Item.
#   2. ESQUEMAS (clases SQLModel sin table=True): representan formas
#      de ENTRADA o SALIDA de datos por la API, sin ser tablas —
#      UserCreate, UserUpdate, ItemCreate, ItemUpdate. Existen para
#      no exponer el modelo de base de datos completo al cliente
#      (por ejemplo, para que nadie pueda mandar su propio `role`
#      al registrarse, o su propio `id` al crear un ítem).
#   3. FUNCIONES DE APOYO: lógica reutilizable (buscar un usuario,
#      saber quién es el usuario autenticado).
#   4. ENDPOINTS: las rutas HTTP en sí (register, login, CRUD, etc).

from datetime import datetime, timedelta, timezone

# Import "a prueba de balas": cuando este archivo se importa como
# parte del paquete `routers` (import relativo, con el punto),
# funciona el primero. Pero si alguna vez corres este archivo suelto
# o desde otro contexto donde el import relativo no tiene sentido,
# cae al segundo (import absoluto). Es un patrón defensivo, no algo
# que necesites replicar siempre — con que entiendas qué hace basta.
try:
    from .database import get_session
except ImportError:  # pragma: no cover
    from database import get_session

from fastapi import APIRouter, Depends, HTTPException, status
# OAuth2PasswordBearer: le dice a FastAPI (y a Swagger) CÓMO se espera
# recibir el token de autenticación (típicamente en el header
# "Authorization: Bearer <token>"), y desde dónde se consigue ese
# token (tokenUrl, el endpoint de login).
# OAuth2PasswordRequestForm: representa el formulario estándar que
# Swagger (y cualquier cliente OAuth2) manda al hacer login —
# básicamente username + password, como application/x-www-form-urlencoded
# (NO como JSON). Por eso el login se recibe distinto a tus otros
# endpoints que sí reciben JSON.
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# jose (python-jose): librería para crear y leer JSON Web Tokens (JWT).
# jwt.encode() arma el token firmado; jwt.decode() lo verifica y lo
# descifra; JWTError es la excepción que lanza si el token es
# inválido, está vencido, o fue firmado con otra clave.
from jose import JWTError, jwt

# passlib: librería para hashear y verificar contraseñas de forma
# segura. CryptContext es el objeto que sabe qué algoritmo usar
# (en este caso "bcrypt", un algoritmo diseñado específicamente para
# ser LENTO a propósito — así, si alguien roba tu base de datos, no
# puede probar millones de contraseñas por segundo contra los hashes).
from passlib.context import CryptContext

# SQLModel combina lo mejor de SQLAlchemy (el motor de base de datos
# de Python) y Pydantic (validación de datos). Por eso una misma
# clase (como `User`) puede ser al mismo tiempo "una tabla SQL" Y
# "un esquema de validación", dependiendo de si le pones table=True.
from sqlmodel import Field, Relationship, SQLModel, Session, desc, asc, select, or_
from typing import List, Optional

# EmailStr: un tipo de dato de Pydantic que valida automáticamente
# que un string tenga formato de correo electrónico (requiere tener
# instalada la librería adicional 'email-validator').
# field_validator: decorador para escribir validaciones personalizadas
# sobre un campo específico de un modelo (ver más abajo, en la
# validación de contraseñas y títulos).
from pydantic import EmailStr, field_validator
import re  # Expresiones regulares: las usamos para revisar que la
           # contraseña tenga mayúscula, minúscula y número.
from typing import Literal  # Restringe un campo a un conjunto fijo de
                             # valores posibles (como un "enum" simple).

# --- CONFIGURACIÓN DE SEGURIDAD ---
# ⚠️ NOTA IMPORTANTE PARA MÁS ADELANTE: esta clave debería vivir en una
# variable de entorno (algo como os.environ["SECRET_KEY"]), nunca
# escrita directo en el código fuente. Si subes este archivo a GitHub
# tal cual, cualquiera podría firmar tokens JWT válidos para tu API.
# Por ahora, mientras aprendes y corres todo en tu máquina, no es
# grave — pero es una de las primeras cosas a corregir antes de que
# este proyecto salga a producción.
SECRET_KEY = "Huelvito2001"
ALGORITHM = "HS256"  # Algoritmo de firma del JWT (HMAC con SHA-256).
ACCESS_TOKEN_DURATION = 4  # minutos que dura el token antes de vencer.

# APIRouter agrupa un conjunto de endpoints relacionados bajo un
# mismo prefijo de URL y los mismos tags (para que Swagger los
# muestre juntos). main.py luego "monta" este router completo con
# app.include_router(...).
router = APIRouter(
    prefix="/AccesoJwt_SQLModel",
    tags=["Acceso SQLModel"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No Encontrado"}},
)

# tokenUrl le dice a Swagger a qué URL exacta debe hacer el POST
# cuando usas el botón "Authorize". scheme_name es el nombre que
# identifica a ESTE esquema de seguridad en particular — importante
# tenerlo único si hay más de un OAuth2PasswordBearer en el proyecto
# (si no, se pisan entre sí en el documento OpenAPI, como descubrimos
# antes con el bug del botón Authorize).
oauth2 = OAuth2PasswordBearer(tokenUrl="/AccesoJwt_SQLModel/login", scheme_name="OAuth2JwtSQLModel")

# Le decimos a passlib que use específicamente bcrypt para hashear
# contraseñas. crypt.hash(...) genera el hash; crypt.verify(...)
# compara una contraseña en texto plano contra un hash guardado.
crypt = CryptContext(schemes=["bcrypt"])


# ============================================================
# MODELOS DE BASE DE DATOS (table=True → son tablas reales)
# ============================================================
class User(SQLModel, table=True):
    """Representa un usuario almacenado en la base de datos.

    Al heredar de SQLModel CON table=True, esta clase es DOS cosas
    a la vez: una tabla SQL real (SQLModel la usa para crear la
    tabla y hacer INSERT/SELECT/UPDATE) y un esquema de validación
    de Pydantic. Por eso, aunque NO usamos `User` directamente como
    entrada de ningún endpoint (para eso están UserCreate/UserUpdate),
    sí la usamos como tipo de retorno y como el objeto que vive en
    memoria representando una fila de la tabla.
    """

    __tablename__ = "users"

    # primary_key=True la convierte en la clave primaria de la tabla
    # (el identificador único de cada fila). index=True crea un índice
    # en la base de datos para que buscar por UserName sea rápido,
    # incluso con muchísimos usuarios.
    UserName: str = Field(primary_key=True, index=True)
    NombreCompleto: str
    email: str
    Activo: bool = True
    password: str  # Acá SIEMPRE guardamos el HASH, nunca la contraseña real.
    role: str = Field(default="user")  # Por defecto, todos los usuarios son 'user'.

    # Relationship no crea una columna en la tabla — es "azúcar
    # sintáctica" de SQLModel/SQLAlchemy para que, dado un objeto
    # User en Python, puedas acceder a `usuario.items` y obtener
    # automáticamente todos los Item cuyo owner_username coincida.
    # cascade="all, delete-orphan" significa: si borras un User,
    # borra también todos sus Items — así no quedan ítems "huérfanos"
    # apuntando a un usuario que ya no existe.
    items: list["Item"] = Relationship(
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Item(SQLModel, table=True):
    """Representa un elemento (nota, tarea, lo que sea) asociado a
    un usuario dueño."""
    __tablename__ = "items"

    # default=None + Optional[int]: dejamos que SQLite asigne el id
    # automáticamente (autoincremental). Si tú mandaras un id
    # explícito, SQLite intentaría usar ESE valor en vez de calcular
    # el siguiente disponible — por eso ItemCreate (más abajo) NO
    # incluye el campo id: el cliente nunca debería poder elegirlo.
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    # foreign_key="users.UserName" es una restricción a nivel de base
    # de datos: SQLite va a RECHAZAR cualquier intento de guardar un
    # Item cuyo owner_username no exista en la tabla users. Es una
    # red de seguridad extra, además de la lógica que ya tenemos en
    # Python.
    owner_username: str = Field(foreign_key="users.UserName")


# ============================================================
# ESQUEMAS DE ENTRADA/SALIDA (sin table=True → NO son tablas,
# solo "formas" de datos para la API)
# ============================================================
# La idea central de esta sección: el cliente NUNCA debería poder
# mandar directamente un objeto `User` o `Item` completo, porque eso
# le daría control sobre campos que son responsabilidad exclusiva
# del servidor (el id autoincremental, el rol de un usuario nuevo,
# quién es el dueño de un ítem, etc.). Por eso existen estos
# "esquemas de entrada": son la Pydantic-forma de decir "esto es
# exactamente lo que el cliente puede mandarme, ni un campo más".

class UserCreate(SQLModel):
    """Datos que un usuario cualquiera puede enviar al registrarse.
    A propósito NO incluye 'role': eso se asigna después, solo por
    un admin, para que nadie pueda auto-asignarse admin al registrarse.
    """
    UserName: str
    NombreCompleto: str
    email: EmailStr  # Valida automáticamente el formato de email.
    password: str

    # @field_validator("password") le dice a Pydantic: "ejecuta esta
    # función cada vez que valides el campo password de esta clase".
    # @classmethod es obligatorio en esta posición por cómo Pydantic
    # implementa estos validadores internamente (no te preocupes por
    # el motivo exacto, solo recuerda ponerlo siempre ahí).
    #
    # La función recibe el valor que mandó el cliente (`value`). Si
    # está todo bien, debe devolverlo con `return value` — eso es lo
    # que queda guardado de verdad. Si algo está mal, en vez de
    # devolver algo, hacemos `raise ValueError(...)`: Pydantic
    # atrapa ese error y FastAPI responde automáticamente con un
    # 422 Unprocessable Entity, mostrando tu mensaje.
    @field_validator("password")
    @classmethod
    def password_segura(cls, value: str) -> str:
        """Exige una contraseña mínimamente robusta."""
        if len(value) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        # re.search(patrón, texto) busca el patrón DENTRO del texto
        # (no tiene que ser desde el principio). Si no lo encuentra,
        # devuelve None, que es "falsy" en Python → por eso el `not`.
        if not re.search(r"[A-Z]", value):      # al menos una mayúscula
            raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
        if not re.search(r"[a-z]", value):      # al menos una minúscula
            raise ValueError("La contraseña debe incluir al menos una letra minúscula.")
        if not re.search(r"\d", value):         # \d = cualquier dígito
            raise ValueError("La contraseña debe contener al menos un número")
        return value


class UserUpdate(SQLModel):
    """Campos opcionales para actualizar un usuario. El patrón
    `campo: tipo | None = None` en TODOS los campos es justamente lo
    que hace posible una actualización PARCIAL (tipo PATCH): si el
    cliente no manda un campo, llega como None, y en el endpoint
    simplemente no lo tocamos. Si lo manda, lo actualizamos.
    """
    NombreCompleto: str | None = None
    email: EmailStr | None = None
    Activo: bool | None = None
    password: str | None = None
    # Literal[...] restringe los valores posibles a EXACTAMENTE esos
    # tres strings. Si alguien manda role="supervisor" (que no está
    # en la lista), Pydantic lo rechaza automáticamente con un 422,
    # sin que tengamos que escribir ningún `if` para validarlo.
    role: Literal["user", "editor", "admin"] | None = None

    @field_validator("password")
    @classmethod
    def password_segura(cls, value: str | None) -> str | None:
        """Mismo validador que en UserCreate, pero con un detalle
        extra: como password es opcional acá, primero hay que revisar
        si el cliente realmente mandó una contraseña nueva. Si no
        mandó nada (value es None), no hay nada que validar — lo
        dejamos pasar tal cual."""
        if value is None:
            return value  # No mandó contraseña nueva, no hay nada que validar

        if len(value) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if not re.search(r"[A-Z]", value):
            raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
        if not re.search(r"[a-z]", value):
            raise ValueError("La contraseña debe incluir al menos una letra minúscula.")
        if not re.search(r"\d", value):
            raise ValueError("La contraseña debe incluir al menos un número.")
        return value


class ItemCreate(SQLModel):
    """Datos que el cliente envía al crear un ítem.
    Sin 'id' (lo genera la base de datos automáticamente) ni
    'owner_username' (se asigna según el usuario autenticado, nunca
    según lo que diga el cliente — así nadie puede crear un ítem
    "a nombre de" otra persona).
    """
    title: str
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_no_vacio(cls, value: str) -> str:
        """Exige que el título no esté vacío ni sea solo espacios.
        .strip() quita espacios al inicio/final; si lo que queda es
        un string vacío, `not value.strip()` da True."""
        if not value.strip():
            raise ValueError("El título no puede estar vacío.")
        return value


class ItemUpdate(SQLModel):
    """Datos que el cliente envía al actualizar un ítem.
    Todos los campos son opcionales para permitir actualizaciones
    parciales (mismo patrón que UserUpdate).
    """
    title: str | None = None
    description: str | None = None

    @field_validator("title")
    @classmethod
    def title_no_vacio(cls, value: str) -> str:
        """Ojo con la diferencia entre estos dos casos, que es sutil
        pero importante:
          - El cliente NO manda el campo 'title' en absoluto → llega
            como None → lo dejamos pasar (no quiere tocar el título).
          - El cliente manda 'title': '' o 'title': '   ' → llega como
            string (no None) → SÍ entra a la validación, se limpia
            con strip(), queda vacío, y lo rechazamos.
        Esa distinción (None = "no me importa este campo" vs texto
        vacío = "quiero poner esto, y está vacío") es exactamente el
        comportamiento correcto para un PATCH bien diseñado.
        """
        if value is None:
            return value  # No mandó título nuevo, no hay nada que validar

        if not value.strip():
            raise ValueError("El título no puede estar vacío.")
        return value


# ============================================================
# FUNCIONES DE APOYO (lógica reutilizable, no son endpoints)
# ============================================================

def search_user(username: str, session: Session) -> User | None:
    """Busca un usuario en la base de datos SQLite por su UserName.

    select(User).where(...) arma una consulta SQL (algo como
    "SELECT * FROM users WHERE UserName = ?") sin ejecutarla todavía
    — es solo la "receta". session.exec(statement) es lo que
    realmente la manda a la base de datos y trae los resultados.
    .first() toma la primera fila que coincida, o None si no hay
    ninguna (en vez de lanzar un error, que es lo que haría .one()).
    """
    statement = select(User).where(User.UserName == username)
    return session.exec(statement).first()


async def current_user(
    token: str = Depends(oauth2), session: Session = Depends(get_session)
) -> User:
    """La dependencia MÁS importante del archivo: a partir del token
    JWT que vino en el header Authorization, determina QUIÉN está
    haciendo la petición.

    Depends(oauth2) hace que FastAPI extraiga automáticamente el
    token del header "Authorization: Bearer <token>" y te lo pase
    como string en el parámetro `token`. Si no viene ningún token,
    FastAPI ya responde 401 antes de que esta función se ejecute.

    Armamos `credentials_exception` una sola vez al principio porque
    la vamos a usar en varios puntos distintos del try/except — así
    no repetimos el mismo bloque de HTTPException tres veces.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # jwt.decode verifica la FIRMA del token usando SECRET_KEY: si
        # alguien intentó fabricar o modificar un token sin conocer
        # esa clave, la firma no va a coincidir y esto lanza JWTError.
        # También revisa automáticamente que el token no haya vencido
        # (el campo "exp" que pusimos al crearlo en /login).
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # "sub" (subject) es el campo estándar de JWT para identificar
        # DE QUIÉN es el token — en nuestro caso, guardamos ahí el
        # UserName (ver la función login más abajo).
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        # "raise ... from exc" conserva el error original como causa,
        # útil para debugging, aunque de cara al cliente solo vea el
        # mensaje genérico de credentials_exception (por seguridad:
        # no le damos pistas de POR QUÉ falló la validación del token).
        raise credentials_exception from exc

    user = search_user(username, session)
    if user is None:
        raise credentials_exception

    if not user.Activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario se encuentra inactivo",
        )

    return user


# Este import va AQUÍ ABAJO (no al principio del archivo) a propósito:
# security.py necesita importar `current_user` y `User` DESDE este
# archivo, y para que eso funcione sin un ImportError circular, esos
# dos nombres ya tienen que existir en este módulo antes de que
# Python llegue a esta línea. Si lo subieras arriba de todo, se
# rompería — es un ejemplo real de cómo el ORDEN de las líneas en un
# archivo de Python puede resolver (o causar) importaciones circulares.
from .security import verify_admin_role, require_role, require_any_role


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, session: Session = Depends(get_session)):
    """Registra un nuevo usuario directamente en la base de datos SQLite.
    El rol siempre se asigna como 'user' — solo un administrador puede
    cambiarlo después (vía change_user_role o update_any_user).
    """
    existing_user = search_user(user_data.UserName, session)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya existe en el sistema",
        )

    # Construimos el User (el modelo de TABLA) a partir de los datos
    # validados en UserCreate (el ESQUEMA de entrada). Este paso de
    # "traducir" de un esquema a otro es exactamente lo que nos
    # protege de que el cliente controle el campo `role`: acá lo
    # fijamos nosotros, a mano, como "user", sin importar qué venga
    # en el request.
    nuevo_usuario = User(
        UserName=user_data.UserName,
        NombreCompleto=user_data.NombreCompleto,
        email=user_data.email,
        # crypt.hash() nunca guarda la contraseña real — genera un
        # hash de un solo sentido (no se puede "deshacer" para
        # recuperar la contraseña original). Por eso el login más
        # abajo usa crypt.verify() en vez de comparar strings.
        password=crypt.hash(user_data.password),
        role="user",
    )

    session.add(nuevo_usuario)   # marca el objeto para guardar
    session.commit()             # ejecuta el INSERT real en la BD
    session.refresh(nuevo_usuario)  # vuelve a leer el objeto desde la
                                     # BD por si algún valor cambió al
                                     # guardarlo (no es crítico acá,
                                     # pero es buena costumbre)

    return {
        "mensaje": "Usuario registrado exitosamente en la BD",
        "usuario": user_data.UserName,
    }


@router.post("/login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Autentica al usuario y devuelve un token de acceso JWT.

    OAuth2PasswordRequestForm = Depends() hace que FastAPI espere un
    formulario (no JSON) con, como mínimo, los campos 'username' y
    'password' — así es como Swagger manda los datos cuando usas el
    botón Authorize.
    """
    user = search_user(form.username, session)

    # crypt.verify(texto_plano, hash_guardado) hashea internamente el
    # texto plano con el MISMO algoritmo (bcrypt) y compara el
    # resultado contra el hash guardado — nunca "desencripta" el hash,
    # porque bcrypt no es reversible.
    if not user or not crypt.verify(form.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales incorrectas",
        )

    # Calculamos cuándo debe vencer el token: "ahora + 4 minutos".
    # datetime.now(timezone.utc) usa UTC a propósito (no la hora local
    # del servidor), para evitar bugs de husos horarios.
    expiration = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_DURATION
    )
    # El "payload" es la información que va DENTRO del token (no está
    # encriptada, solo firmada — cualquiera puede leer un JWT si lo
    # decodifica, por eso nunca va una contraseña ahí dentro; lo único
    # que ponemos es el username y la fecha de vencimiento).
    payload = {"sub": user.UserName, "exp": expiration}
    access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users", status_code=status.HTTP_200_OK)
async def get_all_users(session: Session = Depends(get_session)):
    """Retorna todos los usuarios desde la base de datos.

    Nota: este endpoint NO tiene ninguna protección con Depends —
    cualquiera, autenticado o no, puede llamarlo. Vale la pena que lo
    tengas presente: quizás en algún momento quieras agregarle
    Depends(current_user) como mínimo, para que solo usuarios
    autenticados puedan ver la lista completa.
    """
    statement = select(User)
    users = session.exec(statement).all()  # .all() trae TODAS las filas

    # Armamos la lista a mano, campo por campo, en vez de devolver
    # los objetos User directo — así evitamos exponer el hash de la
    # contraseña en la respuesta, aunque sea solo un hash.
    users_list = []
    for u in users:
        users_list.append({
            "UserName": u.UserName,
            "NombreCompleto": u.NombreCompleto,
            "email": u.email,
            "Activo": u.Activo,
            "role": u.role
        })
    return {"total_usuarios": len(users_list), "usuarios": users_list}


@router.delete("/users/{username}", status_code=status.HTTP_200_OK)
async def delete_specific_user(
    username: str,
    # Depends(verify_admin_role) en vez de Depends(current_user):
    # esta sola línea es la que convierte este endpoint de "cualquier
    # usuario autenticado puede borrar usuarios" a "solo un admin
    # puede hacerlo". FastAPI ejecuta toda la cadena de verify_admin_role
    # (que a su vez depende de current_user) antes de entrar aquí.
    admin: User = Depends(verify_admin_role),
    session: Session = Depends(get_session),
):
    """Elimina un usuario de la base de datos SQLite. Solo administradores."""
    user_to_delete = search_user(username, session)
    if not user_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    session.delete(user_to_delete)
    session.commit()
    return {
        "mensaje": f"El usuario {username} ha sido eliminado de la base de datos.",
        "eliminado_por": admin.UserName,
    }


@router.patch("/users/{username}/role", status_code=status.HTTP_200_OK)
async def change_user_role(
    username: str,
    # Como `nuevo_role` es un string simple (no está en el path, ni
    # es un modelo Pydantic con Body(...)), FastAPI lo interpreta
    # automáticamente como QUERY PARAMETER: en la URL se vería como
    # .../role?nuevo_role=editor, no dentro de un JSON en el body.
    nuevo_role: str,
    admin: User = Depends(require_role("admin")),
    session: Session = Depends(get_session),
):
    """Permite a un administrador cambiar el rol de cualquier usuario."""
    user_to_update = search_user(username, session)
    if not user_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    user_to_update.role = nuevo_role
    session.add(user_to_update)
    session.commit()
    session.refresh(user_to_update)

    return {
        "mensaje": f"Rol de '{username}' actualizado a '{nuevo_role}'",
        "realizado_por": admin.UserName,
    }


@router.get("/users/me")
async def read_users_me(
    token: str = Depends(oauth2), session: Session = Depends(get_session)
):
    """Devuelve la información del usuario autenticado a partir del token JWT.

    💡 Nota para repasar: este endpoint vuelve a escribir A MANO todo
    el proceso de decodificar el token y buscar al usuario — que es
    EXACTAMENTE lo que ya hace la función `current_user`. Sería más
    corto y evitaría duplicar lógica si en vez de `token: str =
    Depends(oauth2)` pusieras directamente `user: User =
    Depends(current_user)` y listo. Que funcione como está no significa
    que sea la forma más limpia — es un buen ejemplo de "código que
    funciona, pero que se podría simplificar reutilizando lo que ya
    tienes".
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = search_user(username, session)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return user


@router.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(
    item_data: ItemCreate,
    # Este patrón `current_user: User = Depends(current_user)` es
    # válido en Python (el parámetro y la función se llaman igual,
    # pero no hay conflicto porque Depends ya evaluó la función ANTES
    # de asignar el resultado al parámetro), aunque puede confundir
    # al leerlo por primera vez. Es simplemente "el usuario autenticado,
    # resuelto llamando a la función current_user".
    current_user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Crea un ítem asociado automáticamente al usuario autenticado."""

    nuevo_item = Item(
        title=item_data.title,
        description=item_data.description,
        # El dueño del ítem se fija según QUIÉN está autenticado, no
        # según lo que el cliente quisiera mandar — por eso
        # ItemCreate ni siquiera tiene un campo owner_username.
        owner_username=current_user.UserName,
        # Noten que no pasamos `id`: queda en None, y SQLite calcula
        # solo el siguiente número disponible al hacer el INSERT.
    )

    session.add(nuevo_item)
    session.commit()
    session.refresh(nuevo_item)
    return {
        "mensaje": "Ítem creado exitosamente",
        "propietario": current_user.UserName,
        "item": nuevo_item,
    }


@router.get("/items/", status_code=status.HTTP_200_OK)
async def get_my_items(
    skip: int = 0,       # cuántos registros "saltar" (para paginación)
    limit: int = 10,      # cuántos registros traer como máximo
    search: str | None = None,  # texto opcional para buscar
    sort_by: str = "id",  # por qué campo ordenar
    order: str = "asc",   # ascendente o descendente
    current_user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Devuelve únicamente los elementos pertenecientes al usuario
    autenticado, con búsqueda, orden y paginación.

    Fíjate que TODOS estos parámetros (skip, limit, search, sort_by,
    order) son simples valores en la URL como query parameters —
    ninguno viene en el path ni en un body — por ejemplo:
    GET /items/?search=luz&sort_by=title&order=desc&skip=0&limit=5
    """
    # Consulta base: SOLO los ítems de ESTE usuario. Esta es la línea
    # que garantiza que nadie vea los ítems de otra persona en este
    # endpoint (a diferencia de update_any_item, que sí deja a
    # admins/editores tocar ítems ajenos).
    base_query = select(Item).where(Item.owner_username == current_user.UserName)

    # Si mandaron texto de búsqueda, agregamos un filtro OR: que el
    # texto aparezca en el título O en la descripción.
    # .ilike("%texto%") es un LIKE case-insensitive (no importa
    # mayúsculas/minúsculas) con comodines a ambos lados, o sea
    # "contiene este texto en cualquier parte".
    if search:
        search_filter = or_(
            Item.title.ilike(f"%{search}%"),
            Item.description.ilike(f"%{search}%")
        )
        base_query = base_query.where(search_filter)

    # Contamos el TOTAL de resultados que coinciden (antes de aplicar
    # la paginación) — así el cliente sabe cuántas páginas hay en total,
    # no solo cuántos le llegaron en esta página.
    total_items = len(session.exec(base_query).all())

    # Elegimos por qué columna ordenar, según lo que pidió el cliente.
    # Si pide algo que no reconocemos, caemos a ordenar por id (un
    # valor por defecto seguro).
    if sort_by == "title":
        sort_column = Item.title
    elif sort_by == "description":
        sort_column = Item.description
    else:
        sort_column = Item.id

    # desc()/asc() son funciones de SQLModel/SQLAlchemy que envuelven
    # la columna para decirle a la base de datos en qué dirección
    # ordenar.
    if order.lower() == "desc":
        base_query = base_query.order_by(desc(sort_column))
    else:
        base_query = base_query.order_by(asc(sort_column))

    # .offset(skip).limit(limit) es la paginación real: "sáltate los
    # primeros `skip` resultados, y de ahí en adelante tráeme como
    # máximo `limit`". Por ejemplo, página 2 con 10 por página sería
    # skip=10, limit=10.
    paginated_statement = base_query.offset(skip).limit(limit)
    items = session.exec(paginated_statement).all()
    return {
        "total_items": total_items,
        "items": items
    }


@router.patch("/items/{item_id}", status_code=status.HTTP_200_OK)
async def update_any_item(
    item_id: int,
    item_update: ItemUpdate,
    # require_any_role("admin", "editor") deja pasar a CUALQUIERA de
    # los dos roles. La diferencia de comportamiento entre uno y otro
    # NO se resuelve acá en el Depends, sino DENTRO de la función
    # (ver el `if caller.role != "admin" and ...` más abajo).
    caller: User = Depends(require_any_role("admin", "editor")),
    session: Session = Depends(get_session)
):
    """Admin puede modificar el ítem de cualquier usuario.
    Editor puede modificar cualquiera, EXCEPTO si el dueño es admin."""
    # session.get(Modelo, clave_primaria) es un atajo para buscar por
    # ID cuando ya sabes la primary key — más directo que armar un
    # select(...).where(...) a mano.
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")

    # Para saber si el DUEÑO del ítem es admin, primero tenemos que
    # averiguar quién es ese dueño (buscar al User por su username).
    owner = search_user(item.owner_username, session)
    # Esta es la regla de negocio completa en una sola línea:
    # "si quien llama NO es admin, Y el dueño del ítem SÍ es admin,
    # entonces prohibido" — un admin siempre puede, y un editor
    # puede siempre que el dueño no sea admin.
    if caller.role != "admin" and owner and owner.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar ítems que pertenecen a un administrador.",
        )

    # Actualización parcial real: solo tocamos los campos que vinieron
    # con un valor distinto de None.
    if item_update.title is not None:
        item.title = item_update.title
    if item_update.description is not None:
        item.description = item_update.description

    session.add(item)
    session.commit()
    session.refresh(item)

    return {
        "mensaje": "Ítem actualizado",
        "editado_por": caller.UserName,
        "item": item,
    }


@router.patch("/users/{username}", status_code=status.HTTP_200_OK)
async def update_any_user(
    username: str,
    user_update: UserUpdate,
    caller: User = Depends(require_any_role("admin", "editor")),
    session: Session = Depends(get_session),
):
    """Admin puede modificar los datos de cualquier usuario.
    Editor puede modificar cualquiera, EXCEPTO a un usuario con rol admin.
    Cambiar el campo 'role' sigue reservado solo para admins, incluso
    DENTRO de este mismo endpoint (ver el chequeo extra más abajo)."""
    target_user = search_user(username, session)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Misma regla que en update_any_item, pero aplicada directo sobre
    # el usuario objetivo (acá no hace falta buscar a un "dueño"
    # aparte, porque el usuario A MODIFICAR es, en sí mismo, el que
    # podría o no ser admin).
    if caller.role != "admin" and target_user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar los datos de un administrador.",
        )

    if user_update.NombreCompleto is not None:
        target_user.NombreCompleto = user_update.NombreCompleto
    if user_update.email is not None:
        target_user.email = user_update.email
    if user_update.Activo is not None:
        target_user.Activo = user_update.Activo
    if user_update.password is not None:
        # Igual que en el registro: nunca guardamos la contraseña tal
        # cual, siempre volvemos a hashearla.
        target_user.password = crypt.hash(user_update.password)
    if user_update.role is not None:
        # Chequeo EXTRA, además del require_any_role de arriba: aunque
        # un editor puede entrar a este endpoint, NO puede tocar el
        # campo role — eso sigue siendo exclusivo de admin. Por eso
        # este `if` vive aquí adentro y no en el Depends.
        if caller.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo un administrador puede cambiar el rol de un usuario.",
            )
        target_user.role = user_update.role

    session.add(target_user)
    session.commit()
    session.refresh(target_user)

    return {
        "mensaje": f"Usuario '{username}' actualizado",
        "editado_por": caller.UserName,
    }


# Endpoint exclusivo para administradores
@router.get("/admin/dashboard", status_code=status.HTTP_200_OK)
async def admin_dashboard(user = Depends(current_user)):
    """Devuelve el panel principal para usuarios con permisos de administrador.

    💡 Nota: este endpoint hace la verificación de rol "a mano" con un
    simple if, en vez de usar Depends(verify_admin_role) como hace
    delete_specific_user. Ambas formas funcionan igual de bien — esta
    es un poco más manual, pero es útil que la compares con la otra
    para ver las dos maneras de lograr lo mismo.
    """
    if getattr(user, "role", "user") != "admin":
        raise HTTPException(status_code=403, detail="No eres admin")

    return {"message": "Panel secreto"}
