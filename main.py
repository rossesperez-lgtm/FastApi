from contextlib import (asynccontextmanager,)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import products, users, jwt_auth_users, jwt_auth_users_SQLModel, basic_auth_users
from database import create_db_and_tables



# 1. Definimos el gestor de ciclo de vida (lifespan)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al iniciar la aplicación."""
    # Código que se ejecuta AL ARRANCAR la aplicación
    #create_db_and_tables()
    yield
    # (Opcional) Código que se ejecutaría al apagar la aplicación


#app = FastAPI()
# 2. Se lo pasamos como argumento a FastAPI
app = FastAPI(lifespan=lifespan)

# Routers
app.include_router(products.router)
app.include_router(users.router)
#app.include_router(jwt_auth_users.router)
app.include_router(jwt_auth_users_SQLModel.router)
#app.include_router(basic_auth_users.router)
app.mount("/statico", StaticFiles(directory="Static"), name="statico")

@app.get("/")
async def root():
    """Return the home message for the API."""   
    return {"mensaje": "¡FastAPI instalado correctamente!" }


@app.get("/url")
async def url():
    """Return a test URL."""
    return {"prueba_url": "https:/www.google.cl"}


#http://127.0.0.1:8000/redoc
#http://127.0.0.1:8000/docs