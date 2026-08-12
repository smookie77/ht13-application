import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from rest_framework.test import APIClient

from apps.accounts import services, tokens

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


def test_registration_creates_unverified_user(api):
    response = api.post(
        "/api/auth/register/",
        {
            "email": "New.Person@Example.com",
            "full_name": "New Person",
            "password": "s3cure-passphrase!",
        },
        format="json",
    )

    assert response.status_code == 201
    user = User.objects.get(email="new.person@example.com")
    assert not user.is_email_verified


def test_registration_does_not_leak_existing_accounts(api, verified_user):
    """Same response for a taken address, so the endpoint cannot be used to
    enumerate who has an account."""
    response = api.post(
        "/api/auth/register/",
        {
            "email": verified_user.email,
            "full_name": "Impostor",
            "password": "s3cure-passphrase!",
        },
        format="json",
    )

    assert response.status_code == 201
    assert User.objects.filter(email=verified_user.email).count() == 1
    assert User.objects.get(email=verified_user.email).full_name == "Test Buyer"


def test_weak_password_is_rejected(api):
    response = api.post(
        "/api/auth/register/",
        {"email": "weak@example.com", "full_name": "Weak", "password": "12345"},
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(email="weak@example.com").exists()


def test_verification_token_round_trip(unverified_user):
    token = tokens.make_verification_token(unverified_user)
    user = services.verify_email(token)
    assert user.is_email_verified


def test_verification_is_idempotent(unverified_user):
    token = tokens.make_verification_token(unverified_user)
    first = services.verify_email(token)
    second = services.verify_email(token)
    assert first.email_verified_at == second.email_verified_at


def test_tampered_token_is_rejected(unverified_user):
    token = tokens.make_verification_token(unverified_user) + "x"
    with pytest.raises(tokens.InvalidVerificationToken):
        services.verify_email(token)


def test_expired_token_is_rejected(unverified_user, monkeypatch):
    token = tokens.make_verification_token(unverified_user)

    def expired(*args, **kwargs):
        raise signing.SignatureExpired("too old")

    monkeypatch.setattr(signing, "loads", expired)
    with pytest.raises(tokens.InvalidVerificationToken):
        services.verify_email(token)


def test_token_stops_working_after_email_change(unverified_user):
    token = tokens.make_verification_token(unverified_user)
    unverified_user.email = "moved@example.com"
    unverified_user.save(update_fields=["email"])

    with pytest.raises(tokens.InvalidVerificationToken):
        services.verify_email(token)


def test_login_and_me(api, verified_user):
    response = api.post(
        "/api/auth/login/",
        {"email": verified_user.email, "password": "s3cure-passphrase!"},
        format="json",
    )
    assert response.status_code == 200

    me = api.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.data["email"] == verified_user.email
    assert me.data["is_email_verified"] is True


def test_login_failure_message_is_generic(api, verified_user):
    wrong_password = api.post(
        "/api/auth/login/",
        {"email": verified_user.email, "password": "not-the-password"},
        format="json",
    )
    unknown_email = api.post(
        "/api/auth/login/",
        {"email": "nobody@example.com", "password": "not-the-password"},
        format="json",
    )

    assert wrong_password.status_code == unknown_email.status_code == 400
    assert str(wrong_password.data) == str(unknown_email.data)


def test_me_requires_authentication(api):
    assert api.get("/api/auth/me/").status_code == 403
