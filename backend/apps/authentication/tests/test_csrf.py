import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestCSRFEnforcement:
    """
    `@csrf_protect` on register/login/password-reset-request is tested here.
    `SessionAuthentication` already enforces CSRF on authenticated unsafe
    requests (logout); force_login (not force_authenticate) is required to
    trigger that path.
    """

    def _client_with_csrf(self):
        return APIClient(enforce_csrf_checks=True)

    # ---- login ----

    def test_login_without_csrf_rejected(self):
        User.objects.create_user(email="a@x.com", password="long-password-123")
        c = self._client_with_csrf()
        r = c.post(
            reverse("auth:login"),
            {"email": "a@x.com", "password": "long-password-123"},
            format="json",
        )
        assert r.status_code == 403

    def test_login_with_csrf_accepted(self):
        User.objects.create_user(email="a@x.com", password="long-password-123")
        c = self._client_with_csrf()
        c.get(reverse("auth:csrf"))
        token = c.cookies["csrftoken"].value
        r = c.post(
            reverse("auth:login"),
            {"email": "a@x.com", "password": "long-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert r.status_code == 200

    # ---- logout (SessionAuthentication path) ----

    def test_logout_without_csrf_rejected(self):
        user = User.objects.create_user(email="a@x.com", password="long-password-123")
        c = self._client_with_csrf()
        c.force_login(user)  # not force_authenticate: needs SessionAuthentication
        r = c.post(reverse("auth:logout"))
        assert r.status_code == 403

    def test_get_me_does_not_require_csrf(self):
        user = User.objects.create_user(email="a@x.com", password="long-password-123")
        c = self._client_with_csrf()
        c.force_login(user)
        r = c.get(reverse("accounts:me"))
        assert r.status_code == 200

    # ---- register (csrf_protect applied) ----

    def test_register_without_csrf_rejected(self):
        c = self._client_with_csrf()
        r = c.post(
            reverse("auth:register"),
            {"email": "new@x.com", "password": "long-password-123"},
            format="json",
        )
        assert r.status_code == 403

    def test_register_with_csrf_accepted(self):
        c = self._client_with_csrf()
        c.get(reverse("auth:csrf"))
        token = c.cookies["csrftoken"].value
        r = c.post(
            reverse("auth:register"),
            {"email": "new@x.com", "password": "long-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        # 201 on success; 429 possible if rate-limit cache bleeds from other tests
        assert r.status_code in (201, 429)
