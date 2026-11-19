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


# ---- Order statuses ------------------------------------------------------


class OrderStatus(models.TextChoices):
    """Spec 6.1 — full enum. Phase 5 uses only PENDING_PAYMENT and CANCELLED."""

    PENDING_PAYMENT = "PENDING_PAYMENT", "Pending payment"
    PAID = "PAID", "Paid"
    PROCESSING = "PROCESSING", "Processing"
    PARTIALLY_SHIPPED = "PARTIALLY_SHIPPED", "Partially shipped"
    SHIPPED = "SHIPPED", "Shipped"
    DELIVERED = "DELIVERED", "Delivered"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Partially refunded"
    REFUNDED = "REFUNDED", "Refunded"
    DISPUTED = "DISPUTED", "Disputed"


# ---- Order ---------------------------------------------------------------


class Order(models.Model):
    """
    Parent order. One per checkout.

    `status` is a cached column derived from `seller_orders`; the source of
    truth is the seller orders. Call `recompute_status()` after any child
    status change. `total_cents` is likewise cached at creation time and
    never recomputed (prices don't change post-order).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=24,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING_PAYMENT,
        db_index=True,
    )
    total_cents = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="SEK")

    shipping_address = models.JSONField(default=dict, blank=True)

    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_cents__gte=0),
                name="order_total_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self) -> str:
        return f"order:{self.id}"

    def recompute_status(self) -> None:
        """
        Cache the derived status. Phase 5 only has all-same transitions
        (creation → PENDING_PAYMENT, cancel → CANCELLED). Mixed statuses
        are Phase 6+ when partial shipping exists.
        """
        statuses = list(self.seller_orders.values_list("status", flat=True))
        if not statuses:
            new_status = OrderStatus.PENDING_PAYMENT
        elif len(set(statuses)) == 1:
            new_status = statuses[0]
        else:
            # Mixed — Phase 6 will refine with per-child semantics.
            new_status = OrderStatus.PENDING_PAYMENT
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])


# ---- SellerOrder ---------------------------------------------------------


class SellerOrder(models.Model):
    """
    One per store in the parent order.

    Phase 7 seller panel will operate on these. Status drives the parent
    Order.status via `Order.recompute_status()`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="seller_orders")
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="seller_orders",
    )
    status = models.CharField(
        max_length=24,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING_PAYMENT,
    )
    subtotal_cents = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="SEK")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "store"], name="seller_order_unique_per_store"
            ),
            models.CheckConstraint(
                condition=Q(subtotal_cents__gte=0),
                name="seller_order_subtotal_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"seller_order:{self.id}"


# ---- OrderItem -----------------------------------------------------------


class OrderItem(models.Model):
    """
    Snapshot of a cart line at order time. Prices, names, and options are
    frozen; catalog changes do not affect existing orders.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller_order = models.ForeignKey(SellerOrder, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    product_name = models.CharField(max_length=200)
    variant_sku = models.CharField(max_length=64)
    variant_options = models.JSONField(default=dict, blank=True)

    unit_price_cents = models.BigIntegerField()
    quantity = models.PositiveSmallIntegerField()
    line_total_cents = models.BigIntegerField()

    tax_class = models.CharField(max_length=32, default="STANDARD")
    tax_rate_percent = models.IntegerField(default=25)
    commission_rate_percent = models.IntegerField()
    commission_rule_version = models.CharField(max_length=32, default="phase5-default")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="order_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(unit_price_cents__gte=0),
                name="order_item_unit_price_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(line_total_cents__gte=0),
                name="order_item_line_total_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.seller_order_id}:{self.variant_sku} x{self.quantity}"


# ---- Status history ------------------------------------------------------


class OrderStatusHistory(models.Model):
    """Append-only. UPDATE/DELETE blocked by DB trigger."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=24, choices=OrderStatus.choices, blank=True)
    to_status = models.CharField(max_length=24, choices=OrderStatus.choices)
    reason = models.CharField(max_length=200, blank=True)
    actor_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.from_status}->{self.to_status}"


class SellerOrderStatusHistory(models.Model):
    """Append-only. UPDATE/DELETE blocked by DB trigger."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller_order = models.ForeignKey(
        SellerOrder, on_delete=models.CASCADE, related_name="status_history"
    )
    from_status = models.CharField(max_length=24, choices=OrderStatus.choices, blank=True)
    to_status = models.CharField(max_length=24, choices=OrderStatus.choices)
    reason = models.CharField(max_length=200, blank=True)
    actor_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.seller_order_id}: {self.from_status}->{self.to_status}"
