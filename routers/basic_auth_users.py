from pydantic import BaseModel
from fastapi import APIRouter,  HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
#from routers import products, users

#app = FastAPI()
router = APIRouter(prefix="/basic_Auth",
                   tags=["Acceso"],
                   responses={status.HTTP_404_NOT_FOUND: {"message": "No Encontrado"}})

oauth2 = OAuth2PasswordBearer(tokenUrl="/basic_Auth/login", scheme_name="OAuth2BasicAuth")

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
        "Activo": False,
        "password": "123456"
    },
    "Huelvis2": {
        "UserName": "Huelvis2",
        "NombreCompleto": "Richard Osses 2",
        "email": "rossesperez@gmail.com",
        "Activo": True,
        "password": "654321"
    }
}


def search_user(username: str) -> UserDB | None:
    """Busca un usuario por nombre y devuelve sus datos si existe."""
    if username in users_db:
        return UserDB(**users_db[username])
    return None

async def current_user(token: str = Depends(oauth2)):
    """Obtiene el usuario autenticado a partir del token recibido."""
    user =  search_user(token)
    if not user :
        raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Credenciales de autenticación inválidas", 
                    headers={"WWW-Authenticate": "Bearer"}
                )
   # return user
    #return {"access_token": user.UserName, "token_type": "bearer"}    
    return User(
        UserName=user.UserName,
        NombreCompleto=user.NombreCompleto,
        email=user.email,
        Activo=user.Activo
    )



@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Autentica un usuario mediante el formulario de inicio de sesión."""
    user_db = users_db.get(form.username)
    if not user_db:
        raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El usuario no es correcto"
                )
    user = search_user(form.username)
    if not form.password ==user.password:
        raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La contraseña es incorrecta"
                )

    if not user.Activo:
        raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario se encuentra inactivo"
                )        

    return {"access_token": form.username, "token_type": "bearer"}

@router.get("/users/me")
async def me(user: User = Depends(current_user)):
    """Devuelve los datos del usuario autenticado."""
    return user