from fastapi import Depends, HTTPException, status
from .jwt_auth_users_SQLModel import current_user, User

def verify_admin_role(user: User =Depends(current_user)):
    """Verifica si el usuario autenticado tiene rol de administrador."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos suficientes para realizar esta acción.",
        )
    return user

    #user_role = getattr(current_user, "role", None) or "user"

def require_role(required_rol:st):
    """Fábrica de dependencias: genera una dependencia que exige un rol específico.
    Uso: Depends(require_role("editor")), Depends(require_role("admin")), etc.
    """    
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role != required_rol:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción."
        )
        return user
    return dependency

def require_any_role(*roles: str):
    """Fábrica de dependencias: exige que el usuario tenga UNO de los roles indicados.
    Uso: Depends(require_any_role("admin", "editor"))
    """

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Esta acción requiere uno de estos roles: {', '.join(roles)}.",
            )
        return user

    return dependency
