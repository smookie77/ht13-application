"""Provider-agnostic object storage.

Ticket PDFs are private documents: they carry a buyer's name and a QR code that
opens the door. Nothing here ever makes an object public - reads go through a
short-lived signed URL, or through our own authenticated view.
"""

from typing import Protocol


class StorageError(Exception):
    pass


class TicketStorage(Protocol):
    def save(self, key: str, content: bytes, content_type: str = "application/pdf") -> str:
        """Store the object and return the key it can be read back with."""
        ...

    def read(self, key: str) -> bytes:
        ...

    def signed_url(self, key: str, expires_in: int = 300) -> str | None:
        """A time-limited direct URL, or None if the backend cannot issue one."""
        ...

    def delete(self, key: str) -> None:
        ...
