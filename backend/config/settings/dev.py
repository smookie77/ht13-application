from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS or ["http://localhost:3000"]  # noqa: F405
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Browsable API is handy while the SPA does not exist yet.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
