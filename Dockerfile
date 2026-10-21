# ============================================================
# Dockerfile — receta para construir la IMAGEN de la API
# ============================================================
# Una imagen es un paquete inmutable con tu código y todo lo necesario
# para ejecutarlo. Cada instrucción crea una "capa" (layer) y Docker
# reutiliza las capas que no cambiaron: por eso el ORDEN importa.

# Imagen base: Python 3.14 en su variante "slim" (Debian mínimo, más liviana).
FROM python:3.14-slim

# PYTHONDONTWRITEBYTECODE: no escribe archivos .pyc dentro del contenedor.
# PYTHONUNBUFFERED: los logs salen al instante (se ven con docker logs).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Carpeta de trabajo dentro del contenedor.
WORKDIR /app

# 1) Primero SOLO la lista de dependencias y su instalación.
#    Esta capa solo se reconstruye si cambia requirements-api.txt, así
#    modificar tu código no vuelve a descargar todas las librerías.
COPY requirements-api.lock .
RUN pip install --no-cache-dir -r requirements-api.lock

# 2) Usuario sin privilegios: si alguien vulnerara la app, no sería root.
RUN useradd --create-home appuser

# 3) Recién ahora el código (lo que excluye .dockerignore queda fuera).
#    --chown deja los archivos a nombre de appuser sin crear una capa extra.
COPY --chown=appuser:appuser . .

USER appuser

# Documenta el puerto en el que escucha la app (no lo publica por sí solo).
EXPOSE 8000

# Arranque: aplica las migraciones pendientes y luego levanta la API.
# --host 0.0.0.0 es obligatorio: con 127.0.0.1 la app solo sería visible
# desde DENTRO del contenedor y nunca desde tu navegador.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
