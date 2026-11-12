from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .emails import send_password_reset_email, send_verification_email
from .models import EmailVerificationToken, PasswordResetToken

User = get_user_model()


def _generate_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _invalidate_previous(user, model):
    model.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@transaction.atomic
def register_user(*, email: str, password: str, first_name: str = "", last_name: str = ""):
    """
    Create a new CUSTOMER user, generate a verification token, and send email.

    Returns (user, raw_token). The raw token is only ever placed in the email
    body; the DB stores only its SHA-256 hash.
    """
    email_norm = email.strip().lower()

    if User.objects.filter(email=email_norm).exists():
        raise ValueError("email_already_registered")

    # Validate password against Django's configured validators.
    user_stub = User(email=email_norm, first_name=first_name, last_name=last_name)
    try:
        validate_password(password, user=user_stub)
    except ValidationError as exc:
        raise ValueError({"password": list(exc.messages)}) from exc

    user = User.objects.create_user(
        email=email_norm,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )

    raw_token = _issue_email_verification_token(user)
    send_verification_email(user=user, raw_token=raw_token)
    return user, raw_token


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def _issue_email_verification_token(user) -> str:
    _invalidate_previous(user, EmailVerificationToken)
    raw, hashed = _generate_token()
    EmailVerificationToken.objects.create(
        user=user,
        token_hash=hashed,
        expires_at=timezone.now() + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS),
    )
    return raw


@transaction.atomic
def verify_email(*, raw_token: str) -> User | None:
    """
    Mark the user verified. Returns the user on success, None on failure.
    Never reveals why the token was rejected (invalid/expired/used).
    """
    if not raw_token:
        return None
    hashed = _hash_token(raw_token)
    try:
        token = EmailVerificationToken.objects.select_for_update().get(token_hash=hashed)
    except EmailVerificationToken.DoesNotExist:
        return None

    now = timezone.now()
    if token.used_at is not None or token.expires_at < now:
        return None

    token.used_at = now
    token.save(update_fields=["used_at"])

    user = token.user
    if not user.is_email_verified:
        user.mark_email_verified()
        user.save(update_fields=["is_email_verified", "email_verified_at"])
    return user


@transaction.atomic
def resend_verification(user) -> bool:
    """
    Issue a new verification token. Returns True if an email was sent,
    False if the user is already verified (no-op, no email).
    """
    if user.is_email_verified:
        return False
    raw_token = _issue_email_verification_token(user)
    send_verification_email(user=user, raw_token=raw_token)
    return True


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def _issue_password_reset_token(user) -> str:
    _invalidate_previous(user, PasswordResetToken)
    raw, hashed = _generate_token()
    PasswordResetToken.objects.create(
        user=user,
        token_hash=hashed,
        expires_at=timezone.now() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_TTL_HOURS),
    )
    return raw


def request_password_reset(*, email: str) -> None:
    """
    Always behaves identically whether the email exists or not, to prevent
    account enumeration. Sends an email only if the user exists.
    """
    email_norm = email.strip().lower()
    try:
        user = User.objects.get(email=email_norm, is_active=True)
    except User.DoesNotExist:
        return

    raw_token = _issue_password_reset_token(user)
    send_password_reset_email(user=user, raw_token=raw_token)


@transaction.atomic
def confirm_password_reset(*, raw_token: str, new_password: str) -> User | None:
    """
    Reset the password using the token. Returns the user on success,
    None on failure.
    """
    if not raw_token:
        return None
    hashed = _hash_token(raw_token)
    try:
        token = PasswordResetToken.objects.select_for_update().get(token_hash=hashed)
    except PasswordResetToken.DoesNotExist:
        return None

    now = timezone.now()
    if token.used_at is not None or token.expires_at < now:
        return None

    user = token.user
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise ValueError({"password": list(exc.messages)}) from exc

    user.set_password(new_password)
    user.save(update_fields=["password"])

    token.used_at = now
    token.save(update_fields=["used_at"])
    return user
