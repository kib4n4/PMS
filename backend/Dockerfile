# backend/Dockerfile

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collects django-unfold's (and every app's) static assets for whitenoise
# to serve — there's no nginx/static-file layer anywhere else in this
# repo. Safe at build time: it only needs STATIC_ROOT write access, not a
# real DJANGO_SECRET_KEY/DB connection (both have dev-safe fallbacks —
# see config/settings.py).
RUN python manage.py collectstatic --noinput

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/healthz/ || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]