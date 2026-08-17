import tempfile

from .base import *  # noqa: F403

DEBUG = False
CELERY_TASK_ALWAYS_EAGER = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Ticket PDFs land in a throwaway directory, so a test run never writes into
# the working tree.
MEDIA_ROOT = tempfile.mkdtemp(prefix="ticketing-test-media-")
