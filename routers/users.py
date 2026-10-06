from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(tags=["Usuarios"])

# Iniciar server: python3.14.exe -m uvicorn users:app --reload


class User(BaseModel):
    """Representa los datos de un usuario."""
    id: int
    Nombre: str
    Apellido: str
    url: str
    edad: int


users_list = [
    {"Nombre": "Richard", "Apellido": "Osses", "url": "www.google.cl"},
    {"Nombre": "Juan ", "Apellido": "Pérez", "url": "www.google.cl"},
    {"Nombre": "Maria", "Apellido": "Gonzalez", "url": "www.google.cl"},
]

USERS_ID_LIST = [
    User(id=1, Nombre="Richard", Apellido="Osses", url="www.google.cl", edad=47),
    User(id=2, Nombre="Juan ", Apellido="Pérez", url="www.google.cl", edad=50),
    User(id=3, Nombre="Maria", Apellido="Gonzalez", url="www.google.cl", edad=20),
]


@router.get("/users")
async def get_users_dict_list():
    """Return the list of users dictionaries."""
    return users_list


@router.get("/usersclass")
async def get_user_instance():
    """Return a user instance."""
    return User(id=1, Nombre="Richard", Apellido="Osses", url="www.google.cl", edad=47)


@router.get("/user/{user_id}")
async def get_user_by_id(user_id: int):
    """Return the user matching the given ID."""
    users = filter(lambda u: u.id == user_id, USERS_ID_LIST)
    try:
        return list(users)[0]
    except IndexError:
        return {"Error": "Id no existe"}


@router.get("/userquery/")
async def user_query(user_id: int):
    """Return the user matching the given ID."""
    users = filter(lambda u: u.id == user_id, USERS_ID_LIST)
    try:
        return list(users)[0]
    except IndexError:
        return {"Error": "Id no existe"}
       
@router.get("/userqueryFuncion/")
async def user_query_function(user_id: int):
    """Return the user matching the given ID using the search helper."""
    # Retorna un usuario utilizando funciones con id
    return search_user(user_id)


def search_user(user_id: int):
    """Busca y retorna el usuario correspondiente al ID indicado."""
    users = filter(lambda u: u.id == user_id, USERS_ID_LIST)
    try:
        return list(users)[0]
    except IndexError:
        return {"Error": "Id no existe"}


# Función que devuelve todos los objetos User
@router.get("/users_class_list/")
async def get_users_class_list():
    """Retorna la lista completa de objetos User."""
    return USERS_ID_LIST


@router.post("/userAdd/", status_code=201)
async def add_user(usuario: User):
    """Agrega un usuario si no existe otro con el mismo ID."""
    resultado = search_user(usuario.id)
    # CORRECCIÓN 1: Usar isinstance para validar correctamente si es una instancia de User
    if isinstance(resultado, User):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="El usuario ya existe"
        )
    
    USERS_ID_LIST.append(usuario)
    return {"Ok": "Registro agregado"}


# PUT: modificar datos del usuario
@router.put("/userMod/")
async def update_user(usuario: User):
    """Actualiza los datos del usuario con el ID indicado."""
    encontrado = False
    for index, saved_user in enumerate(USERS_ID_LIST):
        if saved_user.id == usuario.id:
            USERS_ID_LIST[index] = usuario
            encontrado = True
            break # Salimos del ciclo apenas se actualiza

    if not encontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no existe"
        )
    return {"Ok": "El usuario fue modificado", "usuario": usuario}


# DELETE: eliminar usuario
@router.delete("/userDel/{user_id}")
async def delete_user(user_id: int):
    """Elimina el usuario que corresponde al ID indicado."""
    encontrado = False
    for index, save_user in enumerate(USERS_ID_LIST):
        if save_user.id == user_id:
            del USERS_ID_LIST[index]
            encontrado = True
            break

    if not encontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no existe"
        )
    return {"Ok": "El usuario fue Eliminado"}