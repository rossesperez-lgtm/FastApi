"""Aplicación frontend con Streamlit para consumir la API FastAPI.

Permite registrar usuarios, iniciar sesión y realizar llamadas a
endpoints protegidos usando el token JWT almacenado en la sesión.
"""

# ============================================================
# frontend_app.py — Interfaz web (Streamlit) para tu API FastAPI
# ============================================================
# Cómo correrla:
#   1. En una terminal: uvicorn main:app --reload   (tu API)
#   2. En OTRA terminal: streamlit run frontend_app.py  (este archivo)
#
# Streamlit corre su propio servidor (normalmente en el puerto 8501)
# y, cada vez que el usuario interactúa con algo (un botón, un campo
# de texto), vuelve a ejecutar TODO el script de arriba hacia abajo.
# Por eso usamos st.session_state: es la única forma de "recordar"
# datos (como el token de login) entre una interacción y la siguiente.

import streamlit as st
import requests

# st.secrets lee un archivo .streamlit/secrets.toml (en desarrollo
# local) o la configuración de "Secrets" del panel de Streamlit
# Community Cloud (una vez desplegado) — mismo concepto que el .env
# que usamos para SECRET_KEY, pero con el mecanismo propio de
# Streamlit. Si no existe ningún secreto configurado (por ejemplo,
# la primera vez que corres esto en tu máquina), cae al valor de
# siempre: tu API local.
try:
    API_BASE_URL = st.secrets["API_BASE_URL"]
except Exception:
    API_BASE_URL = "http://127.0.0.1:8000"

TIMEOUT = 10
BASE_URL = f"{API_BASE_URL}/AccesoJwt_SQLModel"


# ------------------------------------------------------------
# FUNCIONES QUE LLAMAN A LA API
# ------------------------------------------------------------
# Las agrupamos todas juntas arriba para separar "cómo le hablamos
# a la API" de "cómo se ve la pantalla" (más abajo). Cada una
# devuelve el objeto Response completo de requests, y quien la
# llama decide qué hacer con el resultado (mostrar error, guardar
# el token, etc.)

def api_register(username, nombre, email, password):
    """Registra un usuario nuevo. Va como JSON porque así lo espera
    el endpoint /register (recibe un UserCreate)."""
    return requests.post(
        f"{BASE_URL}/register",
        json={
            "UserName": username,
            "NombreCompleto": nombre,
            "email": email,
            "password": password,
        },
        timeout=TIMEOUT,
    )


def api_login(username, password):
    """Hace login. OJO: a diferencia de /register, este endpoint
    espera un FORMULARIO (OAuth2PasswordRequestForm), no JSON —
    por eso usamos el parámetro `data=` de requests (form-encoded)
    en vez de `json=`."""
    return requests.post(
        f"{BASE_URL}/login",
        data={"username": username, "password": password},
        timeout=TIMEOUT,
    )


def auth_headers():
    """Arma el header Authorization con el token guardado en la
    sesión. Todas las llamadas a endpoints protegidos lo necesitan."""
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_me():
    """Trae los datos del usuario autenticado (incluye su role)."""
    return authenticated_request("GET", f"{BASE_URL}/users/me")


def api_get_items(search="", sort_by="id", order="asc", skip=0, limit=10):
    """Trae los ítems del usuario autenticado, con búsqueda, orden y
    paginación (se mandan como query parameters, con `params=`).
    skip = cuántos registros saltar; limit = cuántos traer como máximo."""
    return authenticated_request(
        "GET",
        f"{BASE_URL}/items/",
        params={
            "search": search,
            "sort_by": sort_by,
            "order": order,
            "skip": skip,
            "limit": limit,
        },
    )


def api_create_item(title, description):
    """Crea un nuevo ítem para el usuario autenticado."""
    return authenticated_request(
        "POST",
        f"{BASE_URL}/items/",
        json={"title": title, "description": description or None},
    )


def api_update_item(item_id, title, description):
    """PATCH parcial: solo mandamos los campos que realmente cambiaron.
    Si el campo quedó vacío en el formulario, no lo incluimos en el
    body — así no lo pisamos sin querer."""
    body = {}
    if title:
        body["title"] = title
    if description:
        body["description"] = description
    return authenticated_request("PATCH", f"{BASE_URL}/items/{item_id}", json=body)


def api_get_all_users():
    """Obtiene la lista de usuarios registrados desde la API."""
    return requests.get(f"{BASE_URL}/users")


def api_update_user(username, **campos):
    """**campos junta en un diccionario todos los argumentos con
    nombre que le pasen (NombreCompleto=..., email=..., etc.).
    Filtramos los que vengan vacíos antes de mandarlos, para no
    pisar datos sin querer con un PATCH parcial."""
    body = {k: v for k, v in campos.items() if v}
    return authenticated_request("PATCH", f"{BASE_URL}/users/{username}", json=body)


def api_change_role(username, nuevo_role):
    """Cambia el rol de un usuario mediante un PATCH administrativo."""
    return authenticated_request(
        "PATCH",
        f"{BASE_URL}/users/{username}/role",
        params={"nuevo_role": nuevo_role},
    )


def api_delete_user(username):
    return authenticated_request("DELETE", f"{BASE_URL}/users/{username}")


def api_admin_dashboard():
    return authenticated_request("GET", f"{BASE_URL}/admin/dashboard")


def api_refresh():
    """Pide un access token nuevo usando el refresh token guardado."""
    return requests.post(
        f"{BASE_URL}/refresh",
        json={"refresh_token": st.session_state.refresh_token},
        timeout=10,
    )


def authenticated_request(method, url, **kwargs):
    """Envoltorio para toda petición que necesite el token de acceso.

    Si la petición falla con 401 (access token vencido — recuerda que
    dura solo 4 minutos), intenta renovarlo automáticamente llamando a
    /refresh con el refresh_token (que dura días), y si lo logra,
    reintenta la petición original UNA vez, con el token nuevo. El
    usuario nunca se entera de que pasó nada — simplemente la app
    sigue funcionando.

    Si el refresh_token también venció (o no hay sesión), cerramos la
    sesión y avisamos que hay que loguearse de nuevo — ahí sí no queda
    otra que pedir la contraseña.
    """
    headers = kwargs.pop("headers", {})
    headers.update(auth_headers())
    kwargs.setdefault("timeout", 10)
    response = requests.request(method, url, headers=headers, timeout=kwargs.get("timeout", 10), **kwargs)

    if response.status_code == 401 and st.session_state.refresh_token:
        refresh_resp = api_refresh()
        if refresh_resp.ok:
            st.session_state.token = refresh_resp.json()["access_token"]
            headers.update(auth_headers())  # headers con el token ya renovado
            response = requests.request(method, url, headers=headers, timeout=kwargs.get("timeout", 10), **kwargs)
        else:
            st.session_state.token = None
            st.session_state.refresh_token = None
            st.session_state.username = None
            st.session_state.role = None
            st.warning("Tu sesión expiró. Inicia sesión de nuevo.")
            st.rerun()

    return response


# ------------------------------------------------------------
# UTILIDAD: mostrar errores de la API de forma legible
# ------------------------------------------------------------
def mostrar_resultado(response, mensaje_ok="¡Listo!"):
    """Como todos tus endpoints de FastAPI devuelven el error dentro
    de {"detail": "..."}, esta función evita repetir la misma lógica
    de mostrar error/éxito en cada botón."""
    if response.ok:  # .ok es True para códigos 200-299
        st.success(mensaje_ok)
        st.json(response.json())
    else:
        detalle = response.json().get("detail", response.text)
        st.error(f"Error {response.status_code}: {detalle}")


# ------------------------------------------------------------
# ESTADO DE LA SESIÓN (se inicializa solo la primera vez)
# ------------------------------------------------------------
# session_state es un diccionario que Streamlit mantiene vivo entre
# cada "rerun" del script. Sin esto, el token se perdería cada vez
# que el usuario hiciera clic en cualquier botón.
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.refresh_token = None
    st.session_state.username = None
    st.session_state.role = None
if "pagina_items" not in st.session_state:
    st.session_state.pagina_items = 1  # empezamos en la página 1


# ------------------------------------------------------------
# PANTALLA: LOGIN / REGISTRO (si todavía no hay sesión iniciada)
# ------------------------------------------------------------
st.set_page_config(page_title="Mi App", page_icon="🔐")

if st.session_state.token is None:
    st.title("🔐 Acceso")
    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Registrarse"])

    with tab_login:
        with st.form("form_login"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            enviar = st.form_submit_button("Entrar")

        if enviar:
            resp = api_login(username, password)
            if resp.ok:
                datos_login = resp.json()
                st.session_state.token = datos_login["access_token"]
                st.session_state.refresh_token = datos_login["refresh_token"]
                # Apenas tenemos el token, pedimos /users/me para saber
                # el rol — así el menú se arma según corresponda.
                me = api_me()
                if me.ok:
                    datos = me.json()
                    st.session_state.username = datos["UserName"]
                    st.session_state.role = datos["role"]
                st.rerun()  # vuelve a correr el script desde arriba,
                            # ahora con sesión ya guardada
            else:
                st.error(resp.json().get("detail", "Error al iniciar sesión"))

    with tab_registro:
        with st.form("form_registro"):
            r_username = st.text_input("Usuario")
            r_nombre = st.text_input("Nombre completo")
            r_email = st.text_input("Email")
            r_password = st.text_input("Contraseña", type="password")
            r_enviar = st.form_submit_button("Registrarme")

        if r_enviar:
            resp = api_register(r_username, r_nombre, r_email, r_password)
            mostrar_resultado(resp, "Usuario registrado. Ahora puedes iniciar sesión.")

    st.stop()  # corta la ejecución acá: no mostramos nada más si no
               # hay sesión iniciada


# ------------------------------------------------------------
# A PARTIR DE ACÁ: EL USUARIO YA ESTÁ AUTENTICADO
# ------------------------------------------------------------
st.sidebar.markdown(f"**Usuario:** {st.session_state.username}")
st.sidebar.markdown(f"**Rol:** {st.session_state.role}")
if st.sidebar.button("Cerrar sesión"):
    st.session_state.token = None
    st.session_state.refresh_token = None
    st.session_state.username = None
    st.session_state.role = None
    st.rerun()

# El menú cambia según el rol — un usuario normal no ve las opciones
# de administración, porque igual la API se las rechazaría.
opciones = ["Mi perfil", "Mis ítems"]
if st.session_state.role in ("admin", "editor"):
    opciones.append("Administración")
if st.session_state.role == "admin":
    opciones.append("Panel admin")

pagina = st.sidebar.radio("Menú", opciones)

st.title(pagina)

# --- Mi perfil ---
if pagina == "Mi perfil":
    resp = api_me()
    if resp.ok:
        st.json(resp.json())

# --- Mis ítems ---
elif pagina == "Mis ítems":
    st.subheader("Crear nuevo ítem")
    with st.form("form_crear_item"):
        titulo = st.text_input("Título")
        descripcion = st.text_area("Descripción (opcional)")
        crear = st.form_submit_button("Crear")
    if crear:
        resp = api_create_item(titulo, descripcion)
        mostrar_resultado(resp, "Ítem creado")

    st.divider()
    st.subheader("Mis ítems")
    col1, col2, col3 = st.columns(3)
    with col1:
        busqueda = st.text_input("Buscar", key="busqueda_items")
    with col2:
        orden_campo = st.selectbox("Ordenar por", ["id", "title", "description"])
    with col3:
        orden_dir = st.selectbox("Dirección", ["asc", "desc"])

    POR_PAGINA = 10
    # Si el usuario cambió la búsqueda, lo más razonable es volver a
    # la página 1 (si no, podría quedar "parado" en una página 3 que
    # ya ni siquiera existe para la nueva búsqueda).
    if busqueda != st.session_state.get("ultima_busqueda", ""):
        st.session_state.pagina_items = 1
        st.session_state.ultima_busqueda = busqueda

    # skip = cuántos registros saltar según en qué página estemos.
    # Página 1 -> skip 0, página 2 -> skip 10, página 3 -> skip 20, etc.
    skip = (st.session_state.pagina_items - 1) * POR_PAGINA

    resp = api_get_items(busqueda, orden_campo, orden_dir, skip=skip, limit=POR_PAGINA)
    if resp.ok:
        datos = resp.json()
        total = datos["total_items"]
        # -(-a // b) es una forma rápida de "redondear hacia arriba"
        # una división entera en Python (en vez de importar math.ceil).
        total_paginas = max(1, -(-total // POR_PAGINA))

        st.caption(f"Total: {total} ítems — página {st.session_state.pagina_items} de {total_paginas}")

        for item in datos["items"]:
            st.write(f"**#{item['id']} — {item['title']}**: {item['description'] or '(sin descripción)'}")

        # Botones de navegación, uno al lado del otro.
        col_ant, col_info, col_sig = st.columns([1, 2, 1])
        with col_ant:
            if st.button("⬅️ Anterior", disabled=st.session_state.pagina_items <= 1):
                st.session_state.pagina_items -= 1
                st.rerun()
        with col_sig:
            if st.button("Siguiente ➡️", disabled=st.session_state.pagina_items >= total_paginas):
                st.session_state.pagina_items += 1
                st.rerun()

# --- Administración (admin y editor) ---
elif pagina == "Administración":
    st.subheader("Todos los usuarios")
    resp = api_get_all_users()
    if resp.ok:
        st.table(resp.json()["usuarios"])

    st.divider()
    st.subheader("Modificar datos de un usuario")
    with st.form("form_update_user"):
        u_username = st.text_input("Username del usuario a modificar")
        u_nombre = st.text_input("Nuevo nombre completo (opcional)")
        u_email = st.text_input("Nuevo email (opcional)")
        u_actualizar = st.form_submit_button("Actualizar")
    if u_actualizar:
        resp = api_update_user(u_username, NombreCompleto=u_nombre, email=u_email)
        mostrar_resultado(resp, "Usuario actualizado")

    st.divider()
    st.subheader("Modificar un ítem de cualquier usuario")
    with st.form("form_update_item"):
        i_id = st.number_input("ID del ítem", min_value=1, step=1)
        i_titulo = st.text_input("Nuevo título (opcional)", key="edit_title")
        i_desc = st.text_area("Nueva descripción (opcional)", key="edit_desc")
        i_actualizar = st.form_submit_button("Actualizar ítem")
    if i_actualizar:
        resp = api_update_item(int(i_id), i_titulo, i_desc)
        mostrar_resultado(resp, "Ítem actualizado")

# --- Panel admin (solo admin) ---
elif pagina == "Panel admin":
    resp = api_admin_dashboard()
    mostrar_resultado(resp)

    st.divider()
    st.subheader("Cambiar rol de un usuario")
    with st.form("form_rol"):
        rol_username = st.text_input("Username")
        rol_nuevo = st.selectbox("Nuevo rol", ["user", "editor", "admin"])
        rol_enviar = st.form_submit_button("Cambiar rol")
    if rol_enviar:
        resp = api_change_role(rol_username, rol_nuevo)
        mostrar_resultado(resp, "Rol actualizado")

    st.divider()
    st.subheader("⚠️ Eliminar usuario")
    with st.form("form_delete"):
        del_username = st.text_input("Username a eliminar")
        del_enviar = st.form_submit_button("Eliminar", type="primary")
    if del_enviar:
        resp = api_delete_user(del_username)
        mostrar_resultado(resp, "Usuario eliminado")
