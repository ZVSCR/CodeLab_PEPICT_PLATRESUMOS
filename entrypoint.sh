#!/bin/sh
set -e

# Aplica as migrações no banco (Neon) antes de subir o servidor.
# Para pular (ex.: rodar outro comando), use RUN_MIGRATIONS=false.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Aplicando migrações..."
    python manage.py migrate --noinput
fi

# Executa o comando do container (por padrão, o gunicorn definido no Dockerfile)
exec "$@"
