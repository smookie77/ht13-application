"""Provider-agnostic email interface.

Everything in the app sends mail through `EmailSender`, so swapping Resend for
SES (or anything else) is one new class plus one settings change - no caller
has to know.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Attachment:
    filename: str
    content: bytes
    content_type: str = "application/pdf"


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str = ""
    attachments: list[Attachment] = field(default_factory=list)


class EmailSendError(Exception):
    pass


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> str:
        """Deliver the message and return a provider message id."""
        ...
