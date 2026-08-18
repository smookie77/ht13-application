import logging
from pathlib import Path

from django.conf import settings

from .base import StorageError

logger = logging.getLogger(__name__)


class LocalTicketStorage:
    """Development backend: writes under MEDIA_ROOT.

    Cannot issue signed URLs, so `signed_url` returns None and the download
    view streams the bytes itself. That keeps local development free of any
    cloud credentials while exercising the same code path.
    """

    def __init__(self, root: Path | None = None):
        self.root = Path(root or settings.MEDIA_ROOT)

    def _path(self, key: str) -> Path:
        # Keys are built server-side, but a traversal here would write outside
        # MEDIA_ROOT, so it is checked rather than trusted.
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise StorageError("Invalid storage key.")
        return path

    def save(self, key: str, content: bytes, content_type: str = "application/pdf") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        logger.info("Stored %s (%s bytes) locally", key, len(content))
        return key

    def read(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"No stored object for key {key}.") from exc

    def signed_url(self, key: str, expires_in: int = 300) -> str | None:
        return None

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
