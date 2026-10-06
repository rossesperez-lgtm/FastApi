from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# --- 1. Constantes arriba para evitar errores de referencia ---
SECRET_KEY = "Huelvito2001"
ALGORITHM = "HS256"
ACCESS_TOKEN_DURATION = 4

router = APIRouter(
    prefix="/AccesoJwt",
    tags=["Acceso"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No Encontrado"}},
)

# Apuntamos a la ruta completa incluyendo el prefijo del router
oauth2 = OAuth2PasswordBearer(tokenUrl="/AccesoJwt/login", scheme_name="OAuth2JwtUsers")

crypt = CryptContext(schemes=["bcrypt"])


class User(BaseModel):
    """Representa los datos de un usuario."""
    UserName: str
    NombreCompleto: str
    email: str
    Activo: bool


class UserDB(User):
    """Representa los datos de un usuario almacenados en la base de datos."""
    password: str


class UserUpdate(BaseModel):
    """Campos opcionales para actualizar los datos de un usuario."""
    NombreCompleto: str | None = None
    email: str | None = None
    Activo: bool | None = None
    password: str | None = None


users_db = {
    "Huelvis": {
        "UserName": "Huelvis",
        "NombreCompleto": "Richard Osses",
        "email": "rossesperez@gmail.com",
        "Activo": True,
        "password": "$2a$12$ybqEIgwVSFikLhOoakpVoeNCdrf8Dy78nFY3fCvyVPvN5xeBChtkq" # "123456"
    },
    "Huelvis2": {
        "UserName": "Huelvis2",
        "NombreCompleto": "Richard Osses 2",
        "email": "rossesperez@gmail.com",
        "Activo": True,
        "password":  "$2a$12$/1rm.wyY1jVfibK3amEYpOAPayyGLNbLLSnXdC9S5/Mgk2wx.7jIa" # 654321"
    },
}


def search_user(username: str) -> UserDB | None:
    """Busca un usuario por nombre y devuelve sus datos si existe."""
    if username in users_db:
        return UserDB(**users_db[username])
    return None


async def current_user(token: str = Depends(oauth2)) -> User:
    """Valida el token JWT recibido y retorna los datos del usuario autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = search_user(username)
    if user is None:
        raise credentials_exception

    if not user.Activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario se encuentra inactivo",
        )

    return user


@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Autentica un usuario mediante el formulario de inicio de sesión."""
    user = search_user(form.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no es correcto",
        )

    if not crypt.verify(form.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña es incorrecta",
        )

    expiration = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_DURATION
    )

    payload = {"sub": user.UserName, "exp": expiration}

    access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me")
async def me(user: User = Depends(current_user)):
    """Devuelve los datos del usuario autenticado consumiendo el token."""
    user_dict = user.model_dump()
    user_dict.pop("password", None)
    return user_dict

#    return User(
#        UserName=user.UserName,
#        NombreCompleto=user.NombreCompleto,
#        email=user.email,
#        Activo=user.Activo



@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserDB):
    """Registra un nuevo usuario en el diccionario en memoria."""
    if user_data.UserName in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya existe en el sistema",
        )

    hashed_password = crypt.hash(user_data.password)

    users_db[user_data.UserName] = {
        "UserName": user_data.UserName,
        "NombreCompleto": user_data.NombreCompleto,
        "email": user_data.email,
        "Activo": user_data.Activo,
        "password": hashed_password,
    }

    return {
        "mensaje": "Usuario registrado exitosamente",
        "usuario": user_data.UserName,
    }


@router.get("/users", status_code=status.HTTP_200_OK)
async def get_all_users():
    """Retorna una lista con todos los usuarios registrados en el sistema."""
    # Creamos una copia o lista limpia para no exponer las contraseñas hasheadas
    users_list = []
    for username, data in users_db.items():
        # Opcional: creamos un diccionario sin la contraseña por seguridad
        user_data_clean = {
            "UserName": data["UserName"],
            "NombreCompleto": data["NombreCompleto"],
            "email": data["email"],
            "Activo": data["Activo"],
    }
        users_list.append(user_data_clean)
    return {"total_usuarios": len(users_list), "usuarios": users_list}


@router.put("/users/me", status_code=status.HTTP_200_OK)
async def update_my_user(
    user_update: UserUpdate, 
    current_user: User = Depends(current_user)):
    """Permite al usuario autenticado actualizar sus propios datos."""
    db_user_data = users_db.get(current_user.UserName)
    
    if not db_user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Actualizamos solo los campos que el cliente haya enviado
    if user_update.NombreCompleto is not None:
        db_user_data["NombreCompleto"] = user_update.NombreCompleto
    if user_update.email is not None:
        db_user_data["email"] = user_update.email
    if user_update.Activo is not None:
        db_user_data["Activo"] = user_update.Activo
    if user_update.password is not None:
        # Si actualiza la contraseña, debemos volver a hashearla
        db_user_data["password"] = crypt.hash(user_update.password)
        
    return {
        "mensaje": "Datos actualizados exitosamente",
        "usuario": current_user.UserName
    }


@router.delete("/users/{username}", status_code=status.HTTP_200_OK)
async def delete_specific_user(
    username: str, current_user: User = Depends(current_user)
):
    """Elimina un usuario específico validando que exista una sesión activa."""
    if username not in users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    del users_db[username]
    return {
        "mensaje": f"El usuario {username} ha sido eliminado exitosamente.",
        "ejecutado_por": current_user.UserName,
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: User = Depends(current_user)):
    """
    Cierra la sesión del usuario. 
    Nota: Al usar JWT, el cierre de sesión real se completa cuando el cliente 
    elimina el token de su almacenamiento local.
    """
    return {
        "mensaje": f"Sesión cerrada exitosamente para el usuario {current_user.UserName}. Por favor, elimine su token del cliente."
    }


#python3.14 -m pip install --user "passlib[bcrypty]" --break-system-packages

