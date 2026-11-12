from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.views.decorators.csrf import ensure_csrf_cookie
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_action
from apps.authentication import services
from apps.authentication.api.serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    VerifyEmailSerializer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _limited(request) -> bool:
    return getattr(request._request, "limited", False)


def _too_many() -> Response:
    return Response(
        {"detail": "Too many requests. Please try again later."},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


def _dummy_view(request):
    """Callback for CsrfViewMiddleware.process_view; must not set csrf_exempt."""
    return HttpResponse()


def _enforce_csrf(request):
    """
    Run Django's CSRF check explicitly.

    Returns an HttpResponse (403) if CSRF validation fails, None if it passes.
    Call this at the top of POST views that need CSRF but are wrapped in
    DRF's @api_view (which sets csrf_exempt=True on the outer function,
    causing Django's CsrfViewMiddleware to skip the check globally).

    The check is only meaningful on unsafe methods; GET/HEAD/OPTIONS/TRACE
    always pass, so calling this on a GET view is harmless but unnecessary.
    """
    # Reset so process_view actually performs the check.
    request.csrf_processing_done = False
    return CsrfViewMiddleware(_dummy_view).process_view(request, _dummy_view, (), {})


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_view(request):
    return Response({"detail": "CSRF cookie set."})


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@ratelimit(key="ip", rate="3/h", method="POST", block=False)
@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    if (csrf_error := _enforce_csrf(request._request)) is not None:
        return csrf_error
    if _limited(request):
        return _too_many()

    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        user, _raw = services.register_user(
            email=data["email"],
            password=data["password"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
        )
    except ValueError as exc:
        reason = exc.args[0] if exc.args else "registration_failed"
        if isinstance(reason, dict):
            return Response(reason, status=status.HTTP_400_BAD_REQUEST)
        if reason == "email_already_registered":
            return Response({"detail": "Check your email."}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Registration failed."}, status=status.HTTP_400_BAD_REQUEST)

    log_action(
        action="user.registered",
        actor=user,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    return Response({"detail": "Check your email."}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------


@ratelimit(key="ip", rate="5/m", method="POST", block=False)
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    if (csrf_error := _enforce_csrf(request._request)) is not None:
        return csrf_error
    if _limited(request):
        return _too_many()

    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user = authenticate(
        request=request,
        email=data["email"].strip().lower(),
        password=data["password"],
    )
    if user is None or not user.is_active:
        log_action(
            action="login.failed",
            actor_email=data["email"].strip().lower(),
            request=request,
        )
        return Response(
            {"detail": "Invalid email or password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    login(request, user)
    log_action(
        action="login.success",
        actor=user,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    return Response(
        {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "is_email_verified": user.is_email_verified,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    # SessionAuthentication enforces CSRF on this view automatically.
    user = request.user
    log_action(
        action="logout",
        actor=user,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@ratelimit(key="ip", rate="10/h", method="POST", block=False)
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_view(request):
    if _limited(request):
        return _too_many()

    serializer = VerifyEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = services.verify_email(raw_token=serializer.validated_data["token"])
    if user is None:
        return Response(
            {"detail": "Invalid or expired token."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    log_action(
        action="email.verified",
        actor=user,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    return Response({"detail": "Email verified."})


@ratelimit(key="user", rate="3/h", method="POST", block=False)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_verification_view(request):
    if _limited(request):
        return _too_many()

    services.resend_verification(request.user)
    return Response({"detail": "If your email is not verified, a new link has been sent."})


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@ratelimit(key="ip", rate="5/h", method="POST", block=False)
@ratelimit(key="post:email", rate="3/h", method="POST", block=False)
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    if (csrf_error := _enforce_csrf(request._request)) is not None:
        return csrf_error
    if _limited(request):
        return _too_many()

    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"].strip().lower()
    services.request_password_reset(email=email)
    log_action(
        action="password.reset.requested",
        actor_email=email,
        request=request,
    )
    return Response({"detail": "If the address exists, a reset link has been sent."})


@ratelimit(key="ip", rate="5/h", method="POST", block=False)
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    if _limited(request):
        return _too_many()

    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        user = services.confirm_password_reset(
            raw_token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
    except ValueError as exc:
        reason = exc.args[0] if exc.args else "reset_failed"
        if isinstance(reason, dict):
            return Response(reason, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Reset failed."}, status=status.HTTP_400_BAD_REQUEST)

    if user is None:
        return Response(
            {"detail": "Invalid or expired token."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    log_action(
        action="password.reset.completed",
        actor=user,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    return Response({"detail": "Password has been reset."})
