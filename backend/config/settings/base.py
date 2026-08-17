"""Base settings shared by every environment.

Anything environment-specific (debug flags, real credentials, allowed hosts)
is read from the environment - never hardcoded. See `.env.example`.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
)

# Loaded only if present; in production the platform injects real env vars.
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    # Must precede staticfiles so `runserver` serves ASGI and WebSockets work.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    # local
    "apps.accounts",
    "apps.events",
    "apps.ticketing",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}

# A connection pool, not persistent connections.
#
# Under a sales spike every worker thread wants a connection at once. With
# `CONN_MAX_AGE` each one holds its own until it times out, and Postgres hits
# `too many clients already` - which is exactly the failure mode this system is
# supposed to survive. A bounded pool caps what one process can consume and
# hands connections back immediately.
#
# Django treats persistent connections and pooling as mutually exclusive, so
# CONN_MAX_AGE must stay 0 here.
DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["OPTIONS"] = {
    **DATABASES["default"].get("OPTIONS", {}),
    "pool": {
        "min_size": env.int("DB_POOL_MIN_SIZE", default=2),
        "max_size": env.int("DB_POOL_MAX_SIZE", default=10),
        "timeout": env.int("DB_POOL_TIMEOUT", default=10),
    },
}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Celery handles everything that must not block a request: PDF rendering,
# uploads to object storage and outbound email.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_TIME_LIMIT = 120
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Sofia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        # One person cannot machine-gun the queue and crowd out real buyers.
        "reservation-create": env("THROTTLE_RESERVATION_CREATE", default="10/min"),
    },
}

# --- Ticketing rules ---------------------------------------------------------
# How long an allocated ticket is held while the buyer "pays". Short enough
# that abandoned checkouts return to the pool quickly, long enough to finish.
RESERVATION_HOLD_SECONDS = env.int("RESERVATION_HOLD_SECONDS", default=600)
MAX_OPEN_RESERVATIONS_PER_USER = env.int("MAX_OPEN_RESERVATIONS_PER_USER", default=1)

CELERY_BEAT_SCHEDULE = {
    "expire-stale-holds": {
        "task": "ticketing.expire_stale_holds",
        "schedule": 60.0,
    },
}

# --- Integrations ------------------------------------------------------------
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")
EMAIL_SENDER_CLASS = env(
    "EMAIL_SENDER_CLASS",
    default="apps.integrations.email.console.ConsoleEmailSender",
)
RESEND_API_KEY = env("RESEND_API_KEY", default="")
EMAIL_FROM = env("EMAIL_FROM", default="tickets@example.com")

# Ticket PDFs. The bucket is private; downloads go through an authenticated
# view that redirects to a short-lived signed URL.
TICKET_STORAGE_CLASS = env(
    "TICKET_STORAGE_CLASS",
    default="apps.integrations.storage.local.LocalTicketStorage",
)
TICKET_URL_TTL_SECONDS = env.int("TICKET_URL_TTL_SECONDS", default=300)
R2_ACCOUNT_ID = env("R2_ACCOUNT_ID", default="")
R2_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID", default="")
R2_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY", default="")
R2_BUCKET_NAME = env("R2_BUCKET_NAME", default="")

MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))
MEDIA_URL = "media/"

SPECTACULAR_SETTINGS = {
    "TITLE": "Ticketing API",
    "DESCRIPTION": "Ticket sales platform - Hack TUES 13 application task.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# The SPA lives on a different origin, so it needs explicit CORS/CSRF trust.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(levelname)s %(name)s %(message)s"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
