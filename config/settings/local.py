import os

from .base import *  # noqa
from .base import INSTALLED_APPS, MIDDLEWARE

INSTALLED_APPS += [
    "debug_toolbar",
]

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

INTERNAL_IPS = ["127.0.0.1", "localhost"]

ALLOWED_HOSTS = ["*"]

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "debug",
        "PASSWORD": "debug_fduecn2025",
        "USER": "debug",
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "ATOMIC_REQUESTS": False,
    }
}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "celery": {"handlers": ["console"], "level": "INFO"},
        "kombu": {"handlers": ["console"], "level": "INFO"},
    },
}

# Cache settings для локальной разработки
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv(
            "REDIS_URL_FOR_CACHE", default="redis://127.0.0.1:6379/0"
        ),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
            # Игнорировать ошибки Redis в разработке
        },
        "KEY_PREFIX": "local",
        "TIMEOUT": 300,  # 5 минут по умолчанию
    }
}

# Кеширование сессий через Redis
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 86400  # 24 часа

# Настройки для кеширования запросов к БД (опционально)
# SELECT_CACHE_TIMEOUT = 60  # Кешировать результаты SELECT на 60 секунд
