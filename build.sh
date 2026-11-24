#!/usr/bin/env bash
# Executado pelo Render a cada deploy.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# O plano gratuito não tem Shell; por isso o administrador é criado aqui.
# Defina DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL e DJANGO_SUPERUSER_PASSWORD no Render.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --no-input || echo "Administrador já existe."
fi

# Dados fictícios para a apresentação: defina CARREGAR_DEMO=1 no Render.
if [ "$CARREGAR_DEMO" = "1" ]; then
  python manage.py carregar_demo
fi
