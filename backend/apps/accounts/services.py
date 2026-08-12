"""Account business logic.

Views stay thin on purpose: everything here is callable from a test, a
management command or a Celery task without going through HTTP.
"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.integrations.email import EmailMessage, EmailSendError, get_email_sender

from .tokens import (
    InvalidVerificationToken,
    make_verification_token,
    read_verification_token,
    verification_url,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def send_verification_email(user) -> None:
    """Send (or re-send) the confirmation link.

    Failures are logged, not raised: a provider outage must not make an
    otherwise valid registration look broken. The user can always re-request.
    """
    if user.is_email_verified:
        return

    url = verification_url(make_verification_token(user))
    message = EmailMessage(
        to=user.email,
        subject="Confirm your email",
        html=(
            f"<p>Hi {user.get_short_name()},</p>"
            f"<p>Confirm your email address to be able to buy tickets:</p>"
            f'<p><a href="{url}">Confirm my email</a></p>'
            f"<p>The link is valid for 24 hours.</p>"
        ),
        text=f"Confirm your email address: {url}\n\nThe link is valid for 24 hours.",
    )

    try:
        get_email_sender().send(message)
    except EmailSendError:
        logger.exception("Could not send verification email to user %s", user.pk)


@transaction.atomic
def register_user(*, email: str, full_name: str, password: str):
    user = User.objects.create_user(email=email, full_name=full_name, password=password)
    # Only fire the email once the row is safely committed.
    transaction.on_commit(lambda: send_verification_email(user))
    return user


def verify_email(token: str):
    """Confirm an address from a signed token. Idempotent by design - clicking
    the link twice is a success, not an error."""
    payload = read_verification_token(token)

    try:
        user = User.objects.get(pk=payload["uid"])
    except User.DoesNotExist as exc:
        raise InvalidVerificationToken("This verification link is not valid.") from exc

    if user.email != payload.get("email"):
        raise InvalidVerificationToken(
            "The address has changed since this link was sent."
        )

    user.mark_email_verified()
    return user
