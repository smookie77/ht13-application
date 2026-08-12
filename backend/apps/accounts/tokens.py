"""Email verification tokens.

Signed rather than stored: the token carries the user id and is signed with
SECRET_KEY, so there is no table to clean up and no lookup on the hot path.
The signature covers a timestamp, which gives us expiry for free.

Including the current email in the payload means a token stops working if the
address is changed after the mail was sent.
"""

from django.conf import settings
from django.core import signing

SALT = "accounts.email-verification"
MAX_AGE_SECONDS = 60 * 60 * 24  # 24h


class InvalidVerificationToken(Exception):
    pass


def make_verification_token(user) -> str:
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=SALT)


def read_verification_token(token: str) -> dict:
    try:
        return signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.SignatureExpired as exc:
        raise InvalidVerificationToken("This verification link has expired.") from exc
    except signing.BadSignature as exc:
        raise InvalidVerificationToken("This verification link is not valid.") from exc


def verification_url(token: str) -> str:
    """Link into the SPA, which then posts the token back to the API."""
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify-email?token={token}"
