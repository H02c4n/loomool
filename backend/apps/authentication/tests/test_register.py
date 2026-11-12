import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog


@pytest.mark.django_db
class TestRegister:
    def test_creates_unverified_user(self, api_client):
        r = api_client.post(
            reverse("auth:register"),
            {
                "email": "New@Example.com",
                "password": "long-password-123",
                "first_name": "Nia",
            },
            format="json",
        )
        assert r.status_code == 201
        user = User.objects.get(email="new@example.com")
        assert user.is_email_verified is False
        assert user.first_name == "Nia"
        assert user.role == "CUSTOMER"

    def test_sends_verification_email(self, api_client):
        api_client.post(
            reverse("auth:register"),
            {"email": "send@example.com", "password": "long-password-123"},
            format="json",
        )
        assert len(mail.outbox) == 1
        assert "verify" in mail.outbox[0].subject.lower()
        assert "token=" in mail.outbox[0].body

    def test_writes_audit_log(self, api_client):
        api_client.post(
            reverse("auth:register"),
            {"email": "audit@example.com", "password": "long-password-123"},
            format="json",
        )
        entry = AuditLog.objects.get(action="user.registered")
        assert entry.actor_email == "audit@example.com"

    def test_duplicate_email_returns_201_no_enumeration(self, api_client, user):
        r = api_client.post(
            reverse("auth:register"),
            {"email": "user@example.com", "password": "long-password-123"},
            format="json",
        )
        assert r.status_code == 201
        assert len(mail.outbox) == 0

    def test_weak_password_rejected(self, api_client):
        r = api_client.post(
            reverse("auth:register"),
            {"email": "weak@example.com", "password": "short"},
            format="json",
        )
        assert r.status_code == 400
        assert "password" in r.json()
        assert not User.objects.filter(email="weak@example.com").exists()
