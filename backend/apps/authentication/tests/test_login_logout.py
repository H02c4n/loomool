import pytest
from django.urls import reverse

from apps.audit.models import AuditLog


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api_client, user):
        r = api_client.post(
            reverse("auth:login"),
            {"email": "user@example.com", "password": "long-password-123"},
            format="json",
        )
        assert r.status_code == 200
        assert r.json()["email"] == "user@example.com"
        assert "_auth_user_id" in api_client.session

    def test_login_wrong_password(self, api_client, user):
        r = api_client.post(
            reverse("auth:login"),
            {"email": "user@example.com", "password": "wrong-password"},
            format="json",
        )
        assert r.status_code == 400

    def test_login_unknown_email(self, api_client):
        r = api_client.post(
            reverse("auth:login"),
            {"email": "ghost@example.com", "password": "long-password-123"},
            format="json",
        )
        assert r.status_code == 400

    def test_login_cycles_session_key(self, api_client, user):
        api_client.get(reverse("auth:csrf"))
        first_key = api_client.session.session_key

        api_client.post(
            reverse("auth:login"),
            {"email": "user@example.com", "password": "long-password-123"},
            format="json",
        )
        second_key = api_client.session.session_key
        assert second_key and second_key != first_key

    def test_login_writes_audit_logs(self, api_client, user):
        api_client.post(
            reverse("auth:login"),
            {"email": "user@example.com", "password": "long-password-123"},
            format="json",
        )
        assert AuditLog.objects.filter(action="login.success").count() == 1

    def test_login_failure_writes_audit_log(self, api_client, user):
        api_client.post(
            reverse("auth:login"),
            {"email": "user@example.com", "password": "wrong-password"},
            format="json",
        )
        entry = AuditLog.objects.get(action="login.failed")
        assert entry.actor_email == "user@example.com"


@pytest.mark.django_db
class TestLogout:
    def test_logout_requires_auth(self, api_client):
        r = api_client.post(reverse("auth:logout"))
        assert r.status_code in (403, 401)

    def test_logout_flushes_session(self, api_client, user):
        api_client.force_authenticate(user=user)
        api_client.post(reverse("auth:logout"))
        assert "_auth_user_id" not in api_client.session
        assert AuditLog.objects.filter(action="logout").count() == 1
