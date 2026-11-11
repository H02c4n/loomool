import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class RoleChoices(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    SELLER = "SELLER", "Seller"
    SELLER_STAFF = "SELLER_STAFF", "Seller staff"
    SUPPORT = "SUPPORT", "Support"
    FINANCE_ADMIN = "FINANCE_ADMIN", "Finance admin"
    PRODUCT_ADMIN = "PRODUCT_ADMIN", "Product admin"
    SUPER_ADMIN = "SUPER_ADMIN", "Super admin"


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.CUSTOMER,
    )
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email

    def get_short_name(self) -> str:
        return self.first_name or self.email

    def mark_email_verified(self) -> None:
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
