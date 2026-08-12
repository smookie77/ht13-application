from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Email is the identifier here, so the stock username-based manager
    cannot be reused."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # An admin created from the shell has already proven who they are.
        extra_fields.setdefault("email_verified_at", timezone.now())
        if extra_fields["is_staff"] is not True or extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_staff and is_superuser set.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user keyed by email.

    The task requires a confirmed email before a ticket can be issued, and the
    buyer's name goes on the PDF - both are identity concerns, so they live
    here rather than in a side profile table.
    """

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)

    # Timestamp instead of a boolean: it answers "verified?" and "when?" at
    # once, which is what you want when auditing a disputed order.
    email_verified_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    def mark_email_verified(self) -> None:
        if not self.is_email_verified:
            self.email_verified_at = timezone.now()
            self.save(update_fields=["email_verified_at"])

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.email
