# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Бинарник uv (версию при необходимости обновлять вручную)
COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy

# Установим системные зависимости для psycopg2 и Pillow
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev build-essential libjpeg-dev zlib1g-dev postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Создаем непривилегированного пользователя
RUN useradd -m django

WORKDIR /app

# Копируем требуемые зависимости
COPY requirements.txt ./

# Устанавливаем Python зависимости (кэш BuildKit ускоряет повторные сборки)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# Стартовые скрипты и нормализация CRLF (Windows)
COPY --chown=django:django ./compose/prod/entrypoint /entrypoint
COPY --chown=django:django compose/prod/start /start
COPY --chown=django:django compose/prod/start-celery /start-celery
COPY --chown=django:django compose/prod/start-celerybeat /start-celerybeat
COPY --chown=django:django compose/prod/start-flower /start-flower
RUN sed -i 's/\r$//g' /entrypoint /start /start-celery /start-celerybeat /start-flower && \
    chmod +x /entrypoint /start /start-celery /start-celerybeat /start-flower

# Копируем проект
COPY --chown=django:django . .

# Директория логов (в контексте обычно исключена через .dockerignore)
RUN mkdir -p /app/logs && \
    chown django:django /app/logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Открываем порт
EXPOSE 8000

USER django

# Запуск через стартовый скрипт
ENTRYPOINT ["/entrypoint"]
