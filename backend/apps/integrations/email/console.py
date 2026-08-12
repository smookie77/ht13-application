import logging
import uuid

from .base import EmailMessage

logger = logging.getLogger(__name__)


class ConsoleEmailSender:
    """Development sender: logs instead of delivering.

    Prints the body so verification links are clickable straight from the
    runserver output, with no provider account needed to work on the flow.
    """

    def send(self, message: EmailMessage) -> str:
        attachments = ", ".join(a.filename for a in message.attachments) or "none"
        logger.info(
            "\n--- EMAIL ---\nTo: %s\nSubject: %s\nAttachments: %s\n%s\n-------------",
            message.to,
            message.subject,
            attachments,
            message.text or message.html,
        )
        return f"console-{uuid.uuid4()}"
