import base64
import logging

import httpx
from django.conf import settings

from .base import EmailMessage, EmailSendError

logger = logging.getLogger(__name__)

API_URL = "https://api.resend.com/emails"


class ResendEmailSender:
    """Resend transactional email.

    Chosen over SES because it needs no sandbox-exit approval - a real blocker
    when the deadline is an interview date - and its API is a single JSON POST,
    so no SDK has to be trusted or version-pinned.
    """

    def __init__(self, api_key: str | None = None, sender: str | None = None):
        self.api_key = api_key or settings.RESEND_API_KEY
        self.sender = sender or settings.EMAIL_FROM
        if not self.api_key:
            raise EmailSendError("RESEND_API_KEY is not configured.")

    def send(self, message: EmailMessage) -> str:
        payload = {
            "from": self.sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
        }
        if message.text:
            payload["text"] = message.text
        if message.attachments:
            payload["attachments"] = [
                {
                    "filename": a.filename,
                    "content": base64.b64encode(a.content).decode(),
                }
                for a in message.attachments
            ]

        try:
            response = httpx.post(
                API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Never let the provider's response body reach the caller - it can
            # echo recipient addresses into logs the user can see.
            logger.exception("Resend delivery failed for %s", message.to)
            raise EmailSendError("Email delivery failed.") from exc

        return response.json().get("id", "")
