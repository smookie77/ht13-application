from django.contrib.auth import get_user_model, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from .services import register_user, send_verification_email, verify_email
from .tokens import InvalidVerificationToken

User = get_user_model()

# Shared shape for the plain {"detail": "..."} bodies these endpoints return.
DETAIL = inline_serializer("Detail", {"detail": serializers.CharField()})


@extend_schema(
    responses=inline_serializer("Csrf", {"csrfToken": serializers.CharField()}),
)
@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    """Hand the SPA a CSRF cookie before its first unsafe request.

    Sessions are used rather than JWTs kept in JS: the cookie is httpOnly, so a
    XSS bug cannot read the credential. The trade-off is needing CSRF, which
    this endpoint bootstraps.
    """
    return Response({"csrfToken": get_token(request)})


# DRF marks every view csrf_exempt and lets SessionAuthentication re-add the
# check - but only for *authenticated* requests. That leaves the anonymous
# endpoints below open to login/registration CSRF, so they opt back in
# explicitly.
@extend_schema(request=RegisterSerializer, responses={201: DETAIL})
@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    existing = User.objects.filter(email=data["email"]).first()
    if existing:
        # Do not confirm that an address is taken. Re-sending the link is
        # harmless for the real owner and tells an attacker nothing.
        send_verification_email(existing)
    else:
        register_user(**data)

    return Response(
        {"detail": "Check your inbox for a confirmation link."},
        status=status.HTTP_201_CREATED,
    )


@extend_schema(request=VerifyEmailSerializer, responses={200: DETAIL, 400: DETAIL})
@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def verify(request):
    serializer = VerifyEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        user = verify_email(serializer.validated_data["token"])
    except InvalidVerificationToken as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"detail": "Email confirmed.", "user": UserSerializer(user).data})


@extend_schema(request=ResendVerificationSerializer, responses={200: DETAIL})
@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def resend_verification(request):
    serializer = ResendVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = User.objects.filter(email=serializer.validated_data["email"].lower()).first()
    if user:
        send_verification_email(user)

    # Same response either way - no account enumeration.
    return Response({"detail": "If that address is registered, a link is on its way."})


@extend_schema(request=LoginSerializer, responses={200: UserSerializer})
@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def login_view(request):
    serializer = LoginSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    login(request, user)
    return Response(UserSerializer(user).data)


@extend_schema(request=None, responses={204: OpenApiResponse(description="Signed out")})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(responses={200: UserSerializer})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)
