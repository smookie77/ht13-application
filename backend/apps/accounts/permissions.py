from rest_framework.permissions import BasePermission


class IsEmailVerified(BasePermission):
    """Gate for anything that issues a ticket.

    The task requires a confirmed address before a ticket can be obtained, so
    this is enforced server-side on the reservation endpoints - not merely
    hidden in the UI.
    """

    message = "Confirm your email address before buying a ticket."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_email_verified)
