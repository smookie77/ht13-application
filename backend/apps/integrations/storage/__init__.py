from django.conf import settings
from django.utils.module_loading import import_string

from .base import StorageError, TicketStorage

__all__ = ["StorageError", "TicketStorage", "get_ticket_storage"]

_storage_cache: TicketStorage | None = None


def get_ticket_storage() -> TicketStorage:
    """Resolve the configured storage backend once per process."""
    global _storage_cache
    if _storage_cache is None:
        _storage_cache = import_string(settings.TICKET_STORAGE_CLASS)()
    return _storage_cache
