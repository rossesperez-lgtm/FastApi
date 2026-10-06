# ============================================================
# test_auth.py — Tests de registro, login y validaciones
# ============================================================
# Cada función que empieza con "test_" es un test independiente.
# pytest los descubre solos (no hace falta registrarlos en ningún
# lado) con tal de que el archivo se llame test_*.py y las funciones
# test_*.
#
# El patrón que vas a ver en casi todos: "Arrange, Act, Assert"
#   - Arrange: preparar los datos de entrada.
#   - Act: ejecutar la acción que queremos probar (la llamada a la API).
#   - Assert: comprobar que el resultado es el esperado. Si algún
#     `assert` es falso, el test falla y pytest te muestra exactamente
#     cuál y por qué.

import pytest


def test_register_success(client):
    """Registrar con datos válidos debe devolver 201 Created."""
    response = client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": "testuser",
            "NombreCompleto": "Usuario de Prueba",
            "email": "test@example.com",
            "password": "Clave123",
        },
    )
    assert response.status_code == 201
    assert response.json()["usuario"] == "testuser"


def test_register_duplicate_user_fails(client):
    """Registrar dos veces el mismo UserName debe fallar con 400."""
    datos = {
        "UserName": "duplicado",
        "NombreCompleto": "Usuario",
        "email": "dup@example.com",
        "password": "Clave123",
    }
    client.post("/AccesoJwt_SQLModel/register", json=datos)  # primera vez: ok
    response = client.post("/AccesoJwt_SQLModel/register", json=datos)  # segunda: debe fallar

    assert response.status_code == 400


# @pytest.mark.parametrize te deja correr el MISMO test con distintos
# valores de entrada, sin copiar y pegar la función varias veces.
# Cada tupla (email, motivo) genera una ejecución independiente del
# test, con esos valores reemplazando a los parámetros.
@pytest.mark.parametrize(
    "email, motivo",
    [
        ("no-es-un-email", "sin arroba ni dominio"),
        ("falta-dominio@", "falta el dominio después de la arroba"),
        ("@sin-usuario.com", "falta el usuario antes de la arroba"),
    ],
)
def test_register_invalid_email_fails(client, email, motivo):
    """Un email con formato inválido debe rechazarse con 422,
    gracias a que el campo usa EmailStr en UserCreate."""
    response = client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": f"user_{motivo[:5]}",
            "NombreCompleto": "Usuario",
            "email": email,
            "password": "Clave123",
        },
    )
    assert response.status_code == 422, f"Debería rechazar: {motivo}"


@pytest.mark.parametrize(
    "password, motivo",
    [
        ("1234567", "menos de 8 caracteres"),
        ("abcdefgh", "sin mayúscula ni número"),
        ("ABCDEFGH", "sin minúscula ni número"),
        ("Abcdefgh", "sin número"),
    ],
)
def test_register_weak_password_fails(client, password, motivo):
    """Una contraseña que no cumple las reglas debe rechazarse con 422."""
    response = client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": "usuarioclave",
            "NombreCompleto": "Usuario",
            "email": "clave@example.com",
            "password": password,
        },
    )
    assert response.status_code == 422, f"Debería rechazar: {motivo}"


def test_login_success_returns_both_tokens(client):
    """Login con credenciales correctas debe devolver access_token
    y refresh_token."""
    client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": "loguser",
            "NombreCompleto": "Login",
            "email": "login@example.com",
            "password": "Clave123",
        },
    )

    response = client.post(
        "/AccesoJwt_SQLModel/login",
        data={"username": "loguser", "password": "Clave123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_fails(client):
    """Login con contraseña incorrecta debe devolver 400."""
    client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": "loguser2",
            "NombreCompleto": "Login",
            "email": "login2@example.com",
            "password": "Clave123",
        },
    )

    response = client.post(
        "/AccesoJwt_SQLModel/login",
        data={"username": "loguser2", "password": "incorrecta"},
    )

    assert response.status_code == 400


def test_protected_endpoint_without_token_fails(client):
    """Llamar a un endpoint protegido sin ningún token debe dar 401."""
    response = client.get("/AccesoJwt_SQLModel/users/me")
    assert response.status_code == 401


def test_refresh_token_returns_new_access_token(client):
    """El flujo completo de refresh: login → guardar refresh_token →
    pedir un access_token nuevo sin volver a loguearse."""
    client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": "refrescauser",
            "NombreCompleto": "Refresh",
            "email": "refresh@example.com",
            "password": "Clave123",
        },
    )
    login = client.post(
        "/AccesoJwt_SQLModel/login",
        data={"username": "refrescauser", "password": "Clave123"},
    )
    refresh_token = login.json()["refresh_token"]

    response = client.post(
        "/AccesoJwt_SQLModel/refresh", json={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_access_token_cannot_be_used_as_refresh_token(client):
    """Un access_token NO debe servir para pedir un refresh —
    confirma que el campo 'type' dentro del JWT realmente se
    está validando en el endpoint /refresh."""
    client.post(
        "/AccesoJwt_SQLModel/register",
        json={
            "UserName": "mezclauser",
            "NombreCompleto": "Mezcla",
            "email": "mezcla@example.com",
            "password": "Clave123",
        },
    )
    login = client.post(
        "/AccesoJwt_SQLModel/login",
        data={"username": "mezclauser", "password": "Clave123"},
    )
    access_token = login.json()["access_token"]

    response = client.post(
        "/AccesoJwt_SQLModel/refresh", json={"refresh_token": access_token}
    )

    assert response.status_code == 401
