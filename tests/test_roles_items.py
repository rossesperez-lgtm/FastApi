# ============================================================
# test_roles_items.py — Tests de permisos por rol e ítems
# ============================================================
from routers.jwt_auth_users_SQLModel import User, crypt


def registrar_y_loguear(client, username, password="Clave123"):
    """Función de apoyo (NO es un test, por eso no empieza con test_)
    para no repetir en cada test el mismo registro + login + armado
    de headers. Devuelve directamente los headers listos para usar.

    Esto es el mismo principio de "no te repitas" que ya aplicamos en
    el proyecto real con search_user o los validadores compartidos.
    """
    client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": username,
            "NombreCompleto": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    login = client.post(
        "/AccesoJwt_SQLModel/login",
        data={"username": username, "password": password},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def crear_admin_directo(session, username="admin_test"):
    """Como la API, a propósito, no tiene ninguna forma de
    auto-asignarse admin, para los tests creamos uno directo en la
    base de datos de prueba — simulando lo que harías vos a mano con
    SQLite la primera vez en un proyecto real."""
    admin = User(
        UserName=username,
        NombreCompleto="Administrador de prueba",
        email=f"{username}@example.com",
        password=crypt.hash("ClaveAdmin123"),
        role="admin",
    )
    session.add(admin)
    session.commit()
    return admin


def login_headers(client, username, password):
    login = client.post(
        "/AccesoJwt_SQLModel/login", data={"username": username, "password": password}
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------
# Ítems
# ------------------------------------------------------------

def test_create_item_success(client):
    headers = registrar_y_loguear(client, "itemuser")
    response = client.post(
        "/AccesoJwt_SQLModel/items/",
        headers=headers,
        json={"title": "Comprar pan", "description": "Antes de las 18:00"},
    )
    assert response.status_code == 201
    assert response.json()["item"]["title"] == "Comprar pan"


def test_create_item_with_blank_title_fails(client):
    """Confirma la validación de title_no_vacio que armamos antes."""
    headers = registrar_y_loguear(client, "itemuser2")
    response = client.post(
        "/AccesoJwt_SQLModel/items/",
        headers=headers,
        json={"title": "   ", "description": "da igual"},
    )
    assert response.status_code == 422


def test_user_only_sees_their_own_items(client):
    """El usuario A no debe ver los ítems del usuario B en su
    listado — confirma que el filtro por owner_username funciona."""
    headers_a = registrar_y_loguear(client, "usuarioA")
    headers_b = registrar_y_loguear(client, "usuarioB")

    client.post(
        "/AccesoJwt_SQLModel/items/",
        headers=headers_a,
        json={"title": "Ítem de A"},
    )
    client.post(
        "/AccesoJwt_SQLModel/items/",
        headers=headers_b,
        json={"title": "Ítem de B"},
    )

    respuesta_a = client.get("/AccesoJwt_SQLModel/items/", headers=headers_a)
    titulos_de_a = [item["title"] for item in respuesta_a.json()["items"]]

    assert "Ítem de A" in titulos_de_a
    assert "Ítem de B" not in titulos_de_a


# ------------------------------------------------------------
# Permisos por rol
# ------------------------------------------------------------

def test_normal_user_cannot_delete_users(client):
    """Un usuario común, intentando usar un endpoint de admin, debe
    recibir 403 (no 401 — SÍ está autenticado, solo no autorizado)."""
    headers = registrar_y_loguear(client, "usuarionormal")
    registrar_y_loguear(client, "victima")  # otro usuario cualquiera

    response = client.delete("/AccesoJwt_SQLModel/users/victima", headers=headers)

    assert response.status_code == 403


def test_admin_can_delete_users(client, session):
    """Un admin SÍ puede borrar usuarios."""
    crear_admin_directo(session)
    registrar_y_loguear(client, "paraborrar")
    headers_admin = login_headers(client, "admin_test", "ClaveAdmin123")

    response = client.delete(
        "/AccesoJwt_SQLModel/users/paraborrar", headers=headers_admin
    )

    assert response.status_code == 200


def test_editor_cannot_modify_admin_data(client, session):
    """Regla de negocio específica que armamos: un editor puede
    modificar a cualquiera EXCEPTO a un usuario con rol admin."""
    admin = crear_admin_directo(session)

    # Creamos un editor directo en la BD (más simple que pasar por
    # el flujo completo de "admin asciende a alguien" en el test).
    editor = User(
        UserName="editor_test",
        NombreCompleto="Editor de prueba",
        email="editor@example.com",
        password=crypt.hash("ClaveEditor123"),
        role="editor",
    )
    session.add(editor)
    session.commit()

    headers_editor = login_headers(client, "editor_test", "ClaveEditor123")

    response = client.patch(
        f"/AccesoJwt_SQLModel/users/{admin.UserName}",
        headers=headers_editor,
        json={"NombreCompleto": "Intento de cambio"},
    )

    assert response.status_code == 403


def test_only_admin_can_change_role_field(client, session):
    """Aunque un editor SÍ puede entrar al endpoint update_any_user,
    no debe poder tocar específicamente el campo 'role'."""
    crear_admin_directo(session)
    editor = User(
        UserName="editor_test2",
        NombreCompleto="Editor",
        email="editor2@example.com",
        password=crypt.hash("ClaveEditor123"),
        role="editor",
    )
    session.add(editor)
    session.commit()
    registrar_y_loguear(client, "usuario_normal_x")

    headers_editor = login_headers(client, "editor_test2", "ClaveEditor123")

    response = client.patch(
        "/AccesoJwt_SQLModel/users/usuario_normal_x",
        headers=headers_editor,
        json={"role": "admin"},  # un editor NO debería poder hacer esto
    )

    assert response.status_code == 403
