# ============================================================
# security.py — Dependencias de autorización (roles y permisos)
# ============================================================
# Importante distinguir dos conceptos que suenan parecido:
#   - AUTENTICACIÓN (¿quién eres?) → la resuelve `current_user`,
#     que vive en jwt_auth_users_SQLModel.py, validando el JWT.
#   - AUTORIZACIÓN (¿qué puedes hacer, dado quién eres?) → es lo
#     que vive en ESTE archivo: una vez que ya sabemos quién eres,
#     decidimos si tienes permiso para la acción que pediste.
#
# Todo lo de aquí son "dependency factories" o dependencias simples
# que se usan con Depends(...) en los endpoints de los routers.

from fastapi import Depends, HTTPException, status

# OJO con este import: security.py depende de jwt_auth_users_SQLModel.py
# (toma prestado current_user y User). Esto funciona sin ciclo de
# importación porque, del OTRO lado, jwt_auth_users_SQLModel.py importa
# cosas de ESTE archivo (verify_admin_role, require_role, require_any_role)
# recién DESPUÉS de haber definido current_user y User — para cuando
# Python llega a esa línea, los nombres que este archivo necesita ya
# existen. Si movieras ese import al principio del otro archivo, se
# rompería con un ImportError circular.
from .jwt_auth_users_SQLModel import current_user, User


def verify_admin_role(user: User = Depends(current_user)):
    """Dependencia lista para usar: exige que el usuario autenticado
    tenga el rol 'admin'.

    Fíjate en la cadena de Depends: esta función depende de
    `current_user` (que a su vez depende de decodificar el JWT y
    buscar al usuario en la base de datos). Cuando un endpoint hace
    `Depends(verify_admin_role)`, FastAPI resuelve TODA esa cadena
    automáticamente, en orden, antes de ejecutar el endpoint:
    1. Lee el token del header Authorization.
    2. Lo decodifica y busca al usuario (current_user).
    3. Revisa que su rol sea "admin" (esta función).
    4. Si todo pasa, el endpoint recibe el usuario ya autenticado
       y verificado como parámetro.

    Si cualquier paso falla, FastAPI corta ahí mismo con el error
    correspondiente (401 si el token es inválido, 403 si el rol no
    alcanza) y el código del endpoint NUNCA llega a ejecutarse.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos suficientes para realizar esta acción.",
        )
    return user


def require_role(required_role: str):
    """Fábrica de dependencias: en vez de ser ELLA MISMA una
    dependencia, es una función que CONSTRUYE una dependencia a medida,
    según el rol que le pidas.

    La idea de "fábrica" es clave acá: `require_role("editor")` no
    verifica nada todavía — simplemente arma y devuelve una función
    nueva (`dependency`) que, cuando FastAPI la ejecute más adelante,
    va a comparar el rol del usuario contra "editor" específicamente.
    Esto es posible gracias a una CLOSURE: la función interna
    `dependency` "recuerda" el valor de `required_role` aunque
    `require_role` ya haya terminado de ejecutarse hace rato.

    Uso típico en un endpoint:
        Depends(require_role("admin"))
        Depends(require_role("editor"))
    """

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción.",
            )
        return user

    return dependency


def require_any_role(*roles: str):
    """Igual que require_role, pero acepta VARIOS roles válidos en
    vez de uno solo.

    `*roles` es un parámetro variádico: te deja llamar a esta función
    con tantos argumentos como quieras — require_any_role("admin"),
    require_any_role("admin", "editor"), require_any_role("admin",
    "editor", "supervisor")... — y todos quedan juntos dentro de la
    tupla `roles` dentro de la función.

    `user.role not in roles` revisa si el rol del usuario está EN esa
    lista de roles permitidos, sin importar el orden ni cuántos sean.

    Uso típico:
        Depends(require_any_role("admin", "editor"))
    Esto deja pasar tanto a admins como a editores, y dentro del
    propio endpoint luego puedes seguir distinguiendo comportamientos
    distintos para cada rol si hace falta (como hicimos en
    update_any_item y update_any_user).
    """

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Esta acción requiere uno de estos roles: {', '.join(roles)}.",
            )
        return user

    return dependency
