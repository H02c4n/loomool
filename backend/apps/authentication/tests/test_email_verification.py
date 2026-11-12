from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.authentication import services
from apps.authentication.models import EmailVerificationToken


@pytest.mark.django_db
class TestVerifyEmail:
    def _token_for(self, user):
        raw = services._issue_email_verification_token(user)
        return raw

    def test_verifies_user(self, api_client, user):
        raw = self._token_for(user)
        r = api_client.post(reverse("auth:verify_email"), {"token": raw}, format="json")
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.is_email_verified is True
        assert user.email_verified_at is not None
        assert AuditLog.objects.filter(action="email.verified").exists()

    def test_invalid_token(self, api_client, user):
        r = api_client.post(reverse("auth:verify_email"), {"token": "nope"}, format="json")
        assert r.status_code == 400

    def test_expired_token(self, api_client, user):
        raw = self._token_for(user)
        EmailVerificationToken.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        r = api_client.post(reverse("auth:verify_email"), {"token": raw}, format="json")
        assert r.status_code == 400

    def test_token_reuse_fails(self, api_client, user):
        raw = self._token_for(user)
        api_client.post(reverse("auth:verify_email"), {"token": raw}, format="json")
        r = api_client.post(reverse("auth:verify_email"), {"token": raw}, format="json")
        assert r.status_code == 400


@pytest.mark.django_db
class TestResendVerification:
    def test_requires_auth(self, api_client):
        r = api_client.post(reverse("auth:resend_verification"))
        assert r.status_code in (401, 403)

    def test_issues_new_token_and_invalidates_previous(self, api_client, user):
        old_raw = services._issue_email_verification_token(user)
        api_client.force_authenticate(user=user)
        api_client.post(reverse("auth:resend_verification"))

        # Old token no longer usable
        api_client.force_authenticate(user=None)
        r = api_client.post(reverse("auth:verify_email"), {"token": old_raw}, format="json")
        assert r.status_code == 400
        assert len(mail.outbox) >= 1

    def test_already_verified_noop(self, api_client, verified_user):
        api_client.force_authenticate(user=verified_user)
        r = api_client.post(reverse("auth:resend_verification"))
        assert r.status_code == 200
        assert len(mail.outbox) == 0
