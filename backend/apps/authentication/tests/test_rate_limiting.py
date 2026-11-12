import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestRateLimiting:
    def test_register_3_per_hour(self, api_client):
        url = reverse("auth:register")
        for i in range(3):
            r = api_client.post(
                url, {"email": f"a{i}@example.com", "password": "long-password-123"}, format="json"
            )
            assert r.status_code == 201, r.content
        r = api_client.post(
            url, {"email": "a99@example.com", "password": "long-password-123"}, format="json"
        )
        assert r.status_code == 429

    def test_login_5_per_minute(self, api_client, user):
        url = reverse("auth:login")
        for _ in range(5):
            api_client.post(
                url,
                {"email": "user@example.com", "password": "wrong-password"},
                format="json",
            )
        r = api_client.post(
            url,
            {"email": "user@example.com", "password": "wrong-password"},
            format="json",
        )
        assert r.status_code == 429

    def test_password_reset_per_email(self, api_client, user):
        url = reverse("auth:password_reset")
        for _ in range(3):
            api_client.post(url, {"email": "user@example.com"}, format="json")
        r = api_client.post(url, {"email": "user@example.com"}, format="json")
        assert r.status_code == 429

    def test_resend_verification_per_user(self, api_client, user):
        api_client.force_authenticate(user=user)
        url = reverse("auth:resend_verification")
        for _ in range(3):
            api_client.post(url)
        r = api_client.post(url)
        assert r.status_code == 429
