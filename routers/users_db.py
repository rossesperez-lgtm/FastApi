"""User DB Api"""

from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/userdb", 
                   tags=["userdb"],
                   responses={404: {"description": "Not found"}})

# Iniciar server: python3.14.exe -m uvicorn users:app --reload



@router.get("/{id}")
async def get_user_by_id(id: int):
    """Return the user matching the given ID."""
    return search_user(id)


@router.get("/")
async def get_user_by_query_id(id: int):
    """Return the user matching the given ID."""
    return search_user(id)


@router.post("/")
async def create_user(user: User):
    """Add a new user to the list."""
    if type(search_user(user.id)) == User:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Id ya existe")

    users_list.append(user)
    return user

@router.put("/")
async def update_user(user: User):
    """Update the user matching the supplied ID."""
    found = False

    for index, saver in enumerate(users_list):
        if saver.id == user.id:
            users_list[index] = user
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.delete("/{id}")
async def delete_user(id: int):
    """Delete the user with the given ID."""
    found = False
    for index, saver_user in enumerate(users_list):
        if saver_user.id == id:
            del users_list[index]
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

def search_user(user_id: int):
    """Busca y retorna el usuario correspondiente al ID indicado."""
    users = filter(lambda u: u.id == user_id, users_list)
    try:
        return list(users)[0]
    except IndexError:
        return {"Error": "Id no existe"}


