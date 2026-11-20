import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class PaymentStatus(models.TextChoices):
    CREATED = "CREATED", "Created"
    PROCESSING = "PROCESSING", "Processing"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Partially refunded"


class Payment(models.Model):
    """
    One per checkout attempt. A new row is created every time the user
    restarts checkout for the same order (old rows go to FAILED).

    `payment_intent_id` is set when Stripe first returns it — which is
    usually in the webhook, not the session-create response. Hence nullable.

    `amount_cents` is frozen at creation time and never re-read from Stripe;
    reconciliation in Phase 8 compares against Stripe's reported amount.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "shop.Order",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_intent_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, default=None
    )
    checkout_session_id = models.CharField(max_length=255, unique=True)
    amount_cents = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="SEK")
    status = models.CharField(
        max_length=24,
        choices=PaymentStatus.choices,
        default=PaymentStatus.CREATED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_cents__gt=0),
                name="payment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["order", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"payment:{self.id} order:{self.order_id} {self.status}"


class PaymentEvent(models.Model):
    """
    Webhook event log. Idempotency key is `stripe_event_id`.

    `processed_at` is set in a second transaction after the event body is
    applied. If the handler crashes between insert and update, Celery beat
    picks up rows with `processed_at IS NULL` and retries them.

    The `payload` column stores a *minimised* snapshot (IDs and statuses
    only, no PII, no card data) so that bugs can be diagnosed without
    keeping Stripe's full JSON indefinitely.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stripe_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    signature_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["processed_at", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"event:{self.stripe_event_id} {self.event_type}"


class RefundStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"


class Refund(models.Model):
    """
    Admin-initiated full refund. Phase 6 only supports full refunds of a
    single Payment (no partial refunds, no multi-payment orders).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    stripe_refund_id = models.CharField(max_length=255, unique=True)
    amount_cents = models.BigIntegerField()
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=24,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_cents__gt=0),
                name="refund_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"refund:{self.id} payment:{self.payment_id} {self.status}"

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.payment_id and self.amount_cents > self.payment.amount_cents:
            raise ValidationError({"amount_cents": "Refund exceeds the payment amount."})
