from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.authentication import services
from apps.authentication.models import PasswordResetToken


@pytest.mark.django_db
class TestPasswordResetRequest:
    def test_known_email_sends_link(self, api_client, user):
        r = api_client.post(
            reverse("auth:password_reset"),
            {"email": "user@example.com"},
            format="json",
        )
        assert r.status_code == 200
        assert len(mail.outbox) == 1
        assert "reset" in mail.outbox[0].subject.lower()

    def test_unknown_email_returns_200_no_enumeration(self, api_client):
        r = api_client.post(
            reverse("auth:password_reset"),
            {"email": "ghost@example.com"},
            format="json",
        )
        assert r.status_code == 200
        assert len(mail.outbox) == 0

    def test_writes_audit_log(self, api_client, user):
        api_client.post(
            reverse("auth:password_reset"),
            {"email": "user@example.com"},
            format="json",
        )
        assert AuditLog.objects.filter(action="password.reset.requested").exists()


@pytest.mark.django_db
class TestPasswordResetConfirm:
    def _token_for(self, user):
        return services._issue_password_reset_token(user)

    def test_sets_new_password(self, api_client, user):
        raw = self._token_for(user)
        r = api_client.post(
            reverse("auth:password_reset_confirm"),
            {"token": raw, "new_password": "new-long-password-1"},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.check_password("new-long-password-1")

    def test_invalid_token(self, api_client, user):
        r = api_client.post(
            reverse("auth:password_reset_confirm"),
            {"token": "nope", "new_password": "new-long-password-1"},
            format="json",
        )
        assert r.status_code == 400

    def test_expired_token(self, api_client, user):
        raw = self._token_for(user)
        PasswordResetToken.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        r = api_client.post(
            reverse("auth:password_reset_confirm"),
            {"token": raw, "new_password": "new-long-password-1"},
            format="json",
        )
        assert r.status_code == 400

    def test_token_reuse_fails(self, api_client, user):
        raw = self._token_for(user)
        api_client.post(
            reverse("auth:password_reset_confirm"),
            {"token": raw, "new_password": "new-long-password-1"},
            format="json",
        )
        r = api_client.post(
            reverse("auth:password_reset_confirm"),
            {"token": raw, "new_password": "another-long-pass-2"},
            format="json",
        )
        assert r.status_code == 400

    def test_weak_password_rejected(self, api_client, user):
        raw = self._token_for(user)
        r = api_client.post(
            reverse("auth:password_reset_confirm"),
            {"token": raw, "new_password": "short"},
            format="json",
        )
        assert r.status_code == 400
        assert "password" in r.json()

    def test_writes_audit_log(self, api_client, user):
        raw = self._token_for(user)
        api_client.post(
            reverse("auth:password_reset_confirm"),
            {"token": raw, "new_password": "new-long-password-1"},
            format="json",
        )
        assert AuditLog.objects.filter(action="password.reset.completed").exists()
