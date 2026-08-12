from django.conf import settings
from django.utils.module_loading import import_string

from .base import Attachment, EmailMessage, EmailSender, EmailSendError

__all__ = [
    "Attachment",
    "EmailMessage",
    "EmailSender",
    "EmailSendError",
    "get_email_sender",
]

_sender_cache: EmailSender | None = None


def get_email_sender() -> EmailSender:
    """Resolve the configured sender once per process."""
    global _sender_cache
    if _sender_cache is None:
        _sender_cache = import_string(settings.EMAIL_SENDER_CLASS)()
    return _sender_cache
