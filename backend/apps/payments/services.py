from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log_action
from apps.payments import stripe_client
from apps.payments.models import Payment, PaymentStatus, Refund, RefundStatus
from apps.shop.models import Order, OrderStatus
from apps.shop.services import InvalidOrderState

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Base for payment-layer errors."""


class OrderNotFound(PaymentError):
    def __init__(self):
        super().__init__("order_not_found")


class OrderExpired(PaymentError):
    def __init__(self):
        super().__init__("order_expired")


MIN_SESSION_LIFETIME_SECONDS = 31 * 60  # Stripe requires >= 30 min


def _build_success_url(order_id) -> str:
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}/orders/{order_id}/success?session_id={{CHECKOUT_SESSION_ID}}"


def _build_cancel_url(order_id) -> str:
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}/orders/{order_id}/cancel"


@transaction.atomic
def create_checkout_session(*, order, user) -> tuple[Payment, str]:
    """
    Create a Stripe Checkout session for the given order.

    Returns (payment, checkout_url).

    Idempotent on the order: if an open session already exists, its URL is
    returned without creating a new Payment row. If the existing session has
    expired or been completed, it is marked FAILED and a fresh one is created.
    """
    if order.user_id != user.id:
        raise OrderNotFound()

    # Re-fetch under lock so concurrent create/cancel don't race.
    order = Order.objects.select_for_update().get(id=order.id)

    if order.status != OrderStatus.PENDING_PAYMENT:
        raise InvalidOrderState(order.status)

    now = timezone.now()
    if order.expires_at <= now:
        raise OrderExpired()

    existing = (
        Payment.objects.filter(
            order=order,
            status__in=(PaymentStatus.CREATED, PaymentStatus.PROCESSING),
        )
        .order_by("-created_at")
        .first()
    )

    if existing is not None:
        stripe = stripe_client.client()
        try:
            session = stripe.checkout.Session.retrieve(existing.checkout_session_id)
            if getattr(session, "status", None) == "open" and getattr(session, "url", None):
                return existing, session.url
        except Exception as exc:
            # Session gone on Stripe side (expired, deleted, network error).
            # Fall through to create a fresh one; the old Payment row is
            # marked FAILED below.
            logger.info(
                "Checkout session %s could not be retrieved, recreating: %s",
                existing.checkout_session_id,
                exc,
            )

        existing.status = PaymentStatus.FAILED
        existing.save(update_fields=["status", "updated_at"])

    payment = Payment.objects.create(
        order=order,
        amount_cents=order.total_cents,
        currency=order.currency,
        status=PaymentStatus.CREATED,
        checkout_session_id=f"pending-{order.id}-{now.timestamp()}",
    )

    stripe = stripe_client.client()

    stripe_expires_at = max(
        int(now.timestamp()) + MIN_SESSION_LIFETIME_SECONDS,
        int(order.expires_at.timestamp()),
    )

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": order.currency.lower(),
                    "product_data": {"name": f"Kiterpillar order {order.id}"},
                    "unit_amount": order.total_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=_build_success_url(order.id),
        cancel_url=_build_cancel_url(order.id),
        client_reference_id=str(order.id),
        metadata={
            "order_id": str(order.id),
            "payment_id": str(payment.id),
        },
        expires_at=stripe_expires_at,
        idempotency_key=f"checkout-{payment.id}",
    )

    payment.checkout_session_id = session.id
    payment.save(update_fields=["checkout_session_id", "updated_at"])

    log_action(
        action="payment.checkout_created",
        actor=user,
        target_type="order",
        target_id=order.id,
        metadata={"payment_id": str(payment.id), "session_id": session.id},
    )

    return payment, session.url


# ---------------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------------


class PaymentNotRefundable(PaymentError):
    def __init__(self, status: str):
        super().__init__(f"not_refundable:{status}")
        self.status = status


class AlreadyRefunded(PaymentError):
    def __init__(self):
        super().__init__("already_refunded")


class StripeRefundError(PaymentError):
    def __init__(self, message: str):
        super().__init__(f"stripe_error:{message}")


def refund_payment(*, payment: Payment, actor, reason: str = "") -> Refund:
    """
    Issue a full refund for a SUCCEEDED payment via Stripe.

    The Stripe call is made outside the DB transaction so a network failure
    does not hold a row lock. The Refund row is created inside a transaction
    after Stripe accepts; its status starts at PENDING and is moved to
    SUCCEEDED by the `charge.refunded` webhook (single source of truth).

    Idempotency key = `refund-{payment.id}` — retrying the admin action will
    return the existing Stripe refund.
    """

    if payment.status != PaymentStatus.SUCCEEDED:
        raise PaymentNotRefundable(payment.status)

    if not payment.payment_intent_id:
        raise StripeRefundError("missing_payment_intent")

    if Refund.objects.filter(payment=payment, status=RefundStatus.SUCCEEDED).exists():
        raise AlreadyRefunded()

    stripe = stripe_client.client()
    import stripe as stripe_sdk

    try:
        stripe_refund = stripe.Refund.create(
            payment_intent=payment.payment_intent_id,
            idempotency_key=f"refund-{payment.id}",
            reason="requested_by_customer",
        )
    except stripe_sdk.error.StripeError as exc:
        log_action(
            action="payment.refund_failed",
            actor=actor,
            target_type="payment",
            target_id=payment.id,
            metadata={"error": str(exc)},
        )
        raise StripeRefundError(str(exc)) from exc

    with transaction.atomic():
        refund = Refund.objects.create(
            payment=payment,
            stripe_refund_id=stripe_refund.id,
            amount_cents=payment.amount_cents,
            reason=reason or "admin_full_refund",
            status=RefundStatus.PENDING,
        )

        log_action(
            action="payment.refunded",
            actor=actor,
            target_type="payment",
            target_id=payment.id,
            metadata={
                "refund_id": str(refund.id),
                "stripe_refund_id": stripe_refund.id,
                "amount_cents": payment.amount_cents,
            },
        )

    return refund
