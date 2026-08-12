from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf, name="csrf"),
    path("register/", views.register, name="register"),
    path("verify/", views.verify, name="verify-email"),
    path("resend-verification/", views.resend_verification, name="resend-verification"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.me, name="me"),
]
