from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail


def _build_link(path: str, token: str) -> str:
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    qs = urlencode({"token": token})
    return f"{base}{path}?{qs}"


def send_verification_email(*, user, raw_token: str) -> None:
    link = _build_link("/verify-email", raw_token)
    subject = "Verify your Loomool email"
    body = (
        f"Hi {user.first_name or user.email},\n\n"
        f"Please confirm your email address by opening:\n\n{link}\n\n"
        f"The link expires in "
        f"{settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS} hours.\n\n"
        "If you did not sign up for Loomool, ignore this message.\n"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_reset_email(*, user, raw_token: str) -> None:
    link = _build_link("/reset-password", raw_token)
    subject = "Reset your Loomool password"
    body = (
        f"Hi {user.first_name or user.email},\n\n"
        "Someone requested a password reset for your Loomool account.\n\n"
        f"To set a new password, open:\n\n{link}\n\n"
        f"The link expires in {settings.PASSWORD_RESET_TOKEN_TTL_HOURS} hours.\n\n"
        "If this wasn't you, ignore this message.\n"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
