from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    is_email_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "is_email_verified", "date_joined"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150, min_length=2)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        return User.objects.normalize_email(value).lower()

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            self.context.get("request"),
            username=attrs["email"].lower(),
            password=attrs["password"],
        )
        # One message for both wrong-email and wrong-password so the endpoint
        # cannot be used to discover which addresses are registered.
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
