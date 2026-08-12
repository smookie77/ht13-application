from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ("email", "full_name", "is_email_verified", "is_staff", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "full_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        ("Verification", {"fields": ("email_verified_at",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )

    @admin.display(boolean=True, description="Email verified")
    def is_email_verified(self, obj):
        return obj.is_email_verified
