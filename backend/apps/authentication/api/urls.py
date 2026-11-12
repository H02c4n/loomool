from django.urls import path

from . import views

app_name = "auth"

urlpatterns = [
    path("csrf/", views.csrf_view, name="csrf"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verify-email/", views.verify_email_view, name="verify_email"),
    path("resend-verification/", views.resend_verification_view, name="resend_verification"),
    path("password-reset/", views.password_reset_request_view, name="password_reset"),
    path(
        "password-reset/confirm/",
        views.password_reset_confirm_view,
        name="password_reset_confirm",
    ),
]
