import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Cart(models.Model):
    """
    One cart per user (authenticated) OR per session_key (anonymous).

    Exactly one of `user` / `session_key` is set — enforced by CHECK.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )
    session_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(user__isnull=False) & Q(session_key__isnull=True))
                    | (Q(user__isnull=True) & Q(session_key__isnull=False))
                ),
                name="cart_user_xor_session",
            ),
        ]

    def __str__(self) -> str:
        if self.user_id:
            return f"cart:user:{self.user_id}"
        return f"cart:session:{self.session_key}"


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="cart_items",
    )
    quantity = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="cart_item_unique"),
            models.CheckConstraint(
                condition=Q(quantity__gte=1) & Q(quantity__lte=10),
                name="cart_item_quantity_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.cart_id}:{self.variant_id} x{self.quantity}"


class Favorite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="favorite_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.product_id}"
