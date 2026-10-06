from datetime import datetime, timedelta, timezone
import os

try:
    from .database import get_session
except ImportError:  # pragma: no cover
    from database import get_session

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Field, Relationship, SQLModel, Session, desc, asc, select, or_
from typing import List, Optional
from pydantic import EmailStr, field_validator
import re
from typing import Literal

#SECRET_KEY = "Huelvito2001"

# Busca un archivo .env (empezando por la carpeta de este archivo y
# subiendo hacia arriba hasta encontrarlo) y carga su contenido como
# variables de entorno disponibles para os.environ.

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    # Fallar fuerte y claro acá (al arrancar la app) es mucho mejor
    # que dejar que SECRET_KEY quede como None y recibas errores raros
    # de jwt.encode() más adelante, lejos de la causa real.
    raise RuntimeError(
        "Falta la variable de entorno SECRET_KEY. Crea un archivo .env "
        "en la raíz del proyecto con una línea: SECRET_KEY=tu_clave_aqui"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_DURATION = 4
REFRESH_TOKEN_DURATION_DAYS = 7

router = APIRouter(
    prefix="/AccesoJwt_SQLModel",
    tags=["Acceso SQLModel"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No Encontrado"}},
)

oauth2 = OAuth2PasswordBearer(tokenUrl="/AccesoJwt_SQLModel/login", scheme_name="OAuth2JwtSQLModel")
crypt = CryptContext(schemes=["bcrypt"])


def crear_access_token(username: str) -> str:
    """Token de vida corta: se manda en CADA petición a la API."""
    expiration = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_DURATION)
    # El campo "type" es la clave de todo esto: nos deja distinguir,
    # al decodificar, si un token es de acceso o de refresco — así
    # nadie puede usar un refresh_token para llamar a un endpoint
    # protegido directamente, ni usar un access_token para renovar.
    payload = {"sub": username, "exp": expiration, "type": "access"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def crear_refresh_token(username: str) -> str:
    """Token de vida larga: solo sirve para pedir un access_token nuevo."""
    expiration = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DURATION_DAYS)
    payload = {"sub": username, "exp": expiration, "type": "refresh"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)



# --- MODELO DE BASE DE DATOS Y PYDANTIC UNIFICADO ---
class User(SQLModel, table=True):
    """Representa un usuario almacenado en la base de datos."""

    __tablename__ = "users"

    UserName: str = Field(primary_key=True, index=True)
    NombreCompleto: str
    email: str
    Activo: bool = True
    password: str  # Aquí guardaremos el hash de la contraseña
    role: str = Field(default="user")  # Por defecto, todos los usuarios son 'user'

    # Esto crea la relación inversa: desde el usuario podrás ver sus items
    items: list["Item"] = Relationship(
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class Item(SQLModel, table=True):
    """Representa un elemento relacionado con un usuario."""
    __tablename__ = "items"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    # Vinculamos este campo con la tabla "users" usando su Primary Key (UserName)
    owner_username: str = Field(foreign_key="users.UserName")


class RefreshRequest(SQLModel):
    """Lo único que el cliente manda para renovar: su refresh token."""
    refresh_token: str


class UserCreate(SQLModel):
    """Datos que un usuario cualquiera puede enviar al registrarse.
    A propósito NO incluye 'role': eso se asigna después, solo por un admin.
    """
    UserName: str
    NombreCompleto: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_segura(cls, value: str) -> str:
        """Exige una contraseña mínimamente robusta."""
        if len(value) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r"[A-Z]", value):
            raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
        if not re.search(r"[a-z]", value):
            raise ValueError("La contraseña debe incluir al menos una letra minúscula.")
        if not re.search(r"\d", value):
            raise ValueError("La contraseña debe contener al menos un número")
        return value

class UserUpdate(SQLModel):
    """Representa los campos opcionales para actualizar un usuario."""
    NombreCompleto: str | None = None
    email: EmailStr | None = None
    Activo: bool | None = None
    password: str | None = None
    role: Literal["user", "editor", "admin"] | None = None  # Permite actualizar el rol del usuario

    @field_validator("password")
    @classmethod
    def password_segura(cls, value: str | None) -> str | None:
        """Valida la contraseña solo si el cliente envió una nueva contraseña."""
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
    Sin 'id' (lo genera la base de datos) ni 'owner_username'
    (se asigna automáticamente según el usuario autenticado).
    """
    title: str
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_no_vacio(cls, value: str) -> str:
        """Exige que el título no esté vacío."""
        if not value.strip():
            raise ValueError("El título no puede estar vacío.")
        return value

class ItemUpdate(SQLModel):
    """Datos que el cliente envía al actualizar un ítem.
    Todos los campos son opcionales para permitir actualizaciones parciales.
    """
    title: str | None = None
    description: str | None = None

    @field_validator("title")
    @classmethod
    def title_no_vacio(cls, value: str) -> str:
        """Exige que el título no esté vacío."""
        if value is None:
            return value  # No mandó título nuevo, no hay nada que validar

        if not value.strip():
            raise ValueError("El título no puede estar vacío.")
        return value

# --- FUNCIONES DE APOYO CON LA BD ---
def search_user(username: str, session: Session) -> User | None:
    """Busca un usuario en la base de datos SQLite."""
    statement = select(User).where(User.UserName == username)
    return session.exec(statement).first()


async def current_user(
    token: str = Depends(oauth2), session: Session = Depends(get_session)
) -> User:
    """Valida el token JWT y devuelve el usuario autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
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

from .security import verify_admin_role, require_role, require_any_role

# --- ENDPOINTS ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, session: Session = Depends(get_session)):
    """Registra un nuevo usuario directamente en la base de datos SQLite."""
    """ El rol siempre se asigna como 'user'solo un administrador puede cambiarlo después"""
    existing_user = search_user(user_data.UserName, session)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya existe en el sistema",
        )

    # Hasheamos la contraseña antes de guardarla
    #user_data.password = crypt.hash(user_data.password)
    nuevo_usuario = User(
        UserName=user_data.UserName,
        NombreCompleto=user_data.NombreCompleto,
        email=user_data.email,
        password=crypt.hash(user_data.password),
        role="user",
    )    

    session.add(nuevo_usuario)
    session.commit()
    session.refresh(nuevo_usuario)

    return {
        "mensaje": "Usuario registrado exitosamente en la BD",
        "usuario": user_data.UserName,
    }


@router.post("/login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Autentica al usuario y devuelve un token de acceso JWT."""
    user = search_user(form.username, session)

    if not user or not crypt.verify(form.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales incorrectas",
        )
    access_token = crear_access_token(user.UserName)
    refresh_token = crear_refresh_token(user.UserName)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
   
    #expiration = datetime.now(timezone.utc) + timedelta(
    #    minutes=ACCESS_TOKEN_DURATION
    #)
    #payload = {"sub": user.UserName, "exp": expiration}
    #access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    # #return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh")
async def refresh_access_token(
    body: RefreshRequest, session: Session = Depends(get_session)
):
    """Genera un access token nuevo a partir de un refresh token válido,
    sin pedir usuario/contraseña de nuevo."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido o vencido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = search_user(username, session)
    if user is None or not user.Activo:
        raise credentials_exception

    nuevo_access_token = crear_access_token(user.UserName)
    return {"access_token": nuevo_access_token, "token_type": "bearer"}    


@router.get("/users", status_code=status.HTTP_200_OK)
async def get_all_users(session: Session = Depends(get_session)):
    """Retorna todos los usuarios desde la base de datos."""
    statement = select(User)
    users = session.exec(statement).all()

    # Limpiamos las contraseñas para no exponerlas
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
    #current_user: User = Depends(current_user),
    admin: User = Depends(verify_admin_role),  # Verifica que el usuario autenticado sea admin
    session: Session = Depends(get_session),
):
    """Elimina un usuario de la base de datos SQLite."""
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
    """Devuelve la información del usuario autenticado a partir del token JWT."""
    # 1. Decodificamos el token o reutilizamos la función que busca al usuario actual
    # (asumiendo que tienes una función o lógica que valida el token y extrae el username)
    # Por ejemplo, decodificando el JWT para obtener el 'sub' (username):
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

    # 2. Buscamos al usuario en la base de datos SQLite usando la sesión
    user = search_user(username, session)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return user


@router.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(
    item_data: ItemCreate,
    current_user: User = Depends(current_user),  # <-- Inyectamos el usuario autenticado
    session: Session = Depends(get_session),
):
    """Crea un elemento asociado automáticamente al usuario autenticado."""

    nuevo_item = Item(
        title=item_data.title,
        description=item_data.description,
        owner_username=current_user.UserName,  # el id se deja fuera: SQLite lo autogenera
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
    skip: int = 0,      # Registros a saltar (por defecto 0)
    limit: int = 10,    # Límite por página (por defecto 10)
    search: str | None = None, # Parámetro opcional para buscar texto
    sort_by: str ="id", # Parámetro opcional para ordenar por un campo
    order: str = "asc",  # Orden ascendente o descendente
    current_user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Devuelve únicamente los elementos pertenecientes al usuario autenticado."""
    #total_statement = select(Item).where(Item.owner_username == current_user.UserName)
    #total_items = len(session.exec(total_statement).all())
    
    # Consulta para traer ÚNICAMENTE los elementos de la página actual (con skip y limit)
    #paginated_statement = (
    #    select(Item)
    #    .where(Item.owner_username == current_user.UserName)
    #    .offset(skip)
    #    .limit(limit)
    #)
    # 1. Consulta base filtrada por el usuario actual
    base_query = select(Item).where(Item.owner_username == current_user.UserName)
    # Aplicar filtro de búsqueda si existe
    if search:
        search_filter = or_(
            Item.title.ilike(f"%{search}%"),
            Item.description.ilike(f"%{search}%")
        )
        base_query = base_query.where(search_filter)
    
    # Total de elementos que coinciden con los filtros (para la paginación)
    total_items = len(session.exec(base_query).all())

    # Aplicar Ordenamiento (Sorting)
    # Verificamos qué campo se solicitó ordenar
    if sort_by == "title":
        sort_column = Item.title
    elif sort_by == "description":
        sort_column = Item.description
    else:
        sort_column = Item.id  # Por defecto ordenamos por ID
        
    # Aplicamos dirección ascendente o descendente
    if order.lower() == "desc":
        base_query = base_query.order_by(desc(sort_column))
    else:
        base_query = base_query.order_by(asc(sort_column))

    # Aplicamos la paginación (offset y limit) a la consulta
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
    caller: User = Depends(require_any_role("admin", "editor")),
    session: Session = Depends(get_session)
):
    """Admin puede modificar el ítem de cualquier usuario.
    Editor puede modificar cualquiera, EXCEPTO si el dueño es admin."""
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")

    owner = search_user(item.owner_username, session)
    if caller.role != "admin" and owner and owner.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar ítems que pertenecen a un administrador.",
        )

    # Actualizamos solo los campos que se proporcionaron
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
    Cambiar el campo 'role' sigue reservado solo para admins."""
    target_user = search_user(username, session)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

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
        target_user.password = crypt.hash(user_update.password)
    if user_update.role is not None:
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
    """Devuelve el panel principal para usuarios con permisos de administrador."""
    if getattr(user, "role", "user") != "admin":
        raise HTTPException(status_code=403, detail="No eres admin")

    return {"message": "Panel secreto"}




