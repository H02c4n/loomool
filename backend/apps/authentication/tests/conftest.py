import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

User = get_user_model()


class CSRFAPIClient(APIClient):
    """
    APIClient that primes a CSRF cookie on first unsafe request and
    attaches X-CSRFToken automatically. Required for views decorated
    with @csrf_protect (register, login, password-reset-request).
    """

    _csrf_token: str | None = None

    def _ensure_csrf_token(self) -> str:
        if self._csrf_token is None:
            self.get("/api/v1/auth/csrf/")
            self._csrf_token = self.cookies["csrftoken"].value
        return self._csrf_token

    def post(self, path, data=None, format=None, content_type=None, follow=False, **extra):
        if "HTTP_X_CSRFTOKEN" not in extra:
            extra["HTTP_X_CSRFTOKEN"] = self._ensure_csrf_token()
        return super().post(path, data, format, content_type, follow, **extra)


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return CSRFAPIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", password="long-password-123")


@pytest.fixture
def verified_user(db):
    u = User.objects.create_user(email="verified@example.com", password="long-password-123")
    u.mark_email_verified()
    u.save()
    return u
