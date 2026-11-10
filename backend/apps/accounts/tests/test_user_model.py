import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import override_settings

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email(self):
        user = User.objects.create_user(email="Alice@Example.COM", password="long-password-123")
        assert user.email == "alice@example.com"
        assert user.pk is not None
        assert isinstance(user.pk, uuid.UUID)

    def test_email_is_required(self):
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="x")

    def test_email_unique_case_insensitive(self):
        User.objects.create_user(email="alice@example.com", password="pw-12345678901")
        # Manager normalizes to lowercase; the duplicate collides on save().
        # Wrapped in atomic() so the outer pytest transaction stays usable
        # after the IntegrityError aborts the savepoint.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(email="ALICE@example.com", password="pw-12345678902")

    def test_create_superuser(self):
        user = User.objects.create_superuser(email="admin@example.com", password="admin-pw-1234567")
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_create_superuser_rejects_non_staff(self):
        with pytest.raises(ValueError):
            User.objects.create_superuser(email="x@example.com", password="x", is_staff=False)

    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"])
    def test_password_uses_argon2(self):
        user = User.objects.create_user(email="argon@example.com", password="long-password-123")
        assert user.password.startswith("argon2$")

    def test_password_is_hashed(self):
        user = User.objects.create_user(
            email="hash@example.com", password="plaintext-is-never-stored"
        )
        assert user.password != "plaintext-is-never-stored"
        assert user.check_password("plaintext-is-never-stored") is True
