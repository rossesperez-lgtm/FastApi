from pydantic import BaseModel
from fastapi import APIRouter,  HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

ALGORITHM = "HS256"
ACCESS_TOKEN_DURATION = 1

router = APIRouter(prefix="/AccesoJwt",
                   tags=["Accesso"],
                   responses={status.HTTP_404_NOT_FOUND: {"message": "No Encontrado"}})


oauth2 = OAuth2PasswordBearer(tokenUrl="login")

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
        "password": "$2a$12$/1rm.wyY1jVfibK3amEYpOAPayyGLNbLLSnXdC9S5/Mgk2wx.7jIa" #654321"
    }
}


def search_user(username: str) -> UserDB | None:
    """Busca un usuario por nombre y devuelve sus datos si existe."""
    if username in users_db:
        return UserDB(**users_db[username])
    return None

def search_user_db(username: str) -> UserDB | None:
    """Busca un usuario en la base de datos y devuelve sus datos si existe."""
    if username in users_db:
        return UserDB(**users_db[username])
    return None

async def current_user(token: str = Depends(oauth2)) -> User:
    """Valida el token JWT recibido y retorna los datos del usuario autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        # Decodificamos y validamos el token usando la clave secreta y el algoritmo
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    # Buscamos al usuario en la base de datos
    user = search_user(username) # Aquí puedes usar tu función search_user original para retornar el modelo User limpio
    if user is None:
        raise credentials_exception
        
    if not user.Activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario se encuentra inactivo"
        )

    return user



SECRET_KEY = "Huelvito2001"
# Asegúrate de tener tu clave secreta definida arriba

@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Autentica un usuario mediante el formulario de inicio de sesión."""
    user = search_user_db(form.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no es correcto"
        )

    # 2. Verificamos la contraseña usando el atributo correcto (.password)
    if not crypt.verify(form.password, user.password):
        raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La contraseña es incorrecta"
                )

    # 3. Creamos el payload y codificamos el JWT real con jwt.encode
    expiration = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_DURATION)

    payload = {
        "sub": user.UserName, # Usamos UserName con la capitalización correcta del modelo
        "exp": expiration
    }

    access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

   # access_token = {"sub": user.username, 
   #                "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_DURATION)}

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



@router.post("/register",status_code=status.HTTP_201_CREATED)
async def register(user_data: UserDB):
    """Registra un nuevo usuario en el diccionario en memoria."""
    # 1. Verificar si el usuario ya existe
    if user_data.UserName in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuarui ya existe en el sistema"
        )

    # 2. Encriptar la contraseña en texto plano que viene del cliente
    hashed_password = crypt.hash(user_data.password)

# 3. Guardar el usuario con su contraseña ya encriptada (hash)
    users_db[user_data.UserName] = {
        "UserName": user_data.UserName,
        "NombreCompleto": user_data.NombreCompleto,
        "email":user_data.email,
        "Activo":user_data.Activo,
        "password":hashed_password
    }

    return{
        "mensaje": "Usuario registrado exitosamente",
        "usuario": user_data.UserName
    }

#python3.14 -m pip install --user "passlib[bcrypty]" --break-system-packages