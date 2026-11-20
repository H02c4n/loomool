from __future__ import annotations

import logging

from apps.audit.services import log_action
from apps.payments import stripe_client  # noqa: F401 — used by callers to configure
from apps.payments.models import Payment, PaymentStatus
from apps.shop.models import Order
from apps.shop.services import InvalidOrderState, mark_order_paid

logger = logging.getLogger(__name__)


def handle_event(event: dict) -> None:
    """Dispatch a verified Stripe event. Caller owns the transaction."""
    event_type = event.get("type", "")
    handler = _HANDLERS.get(event_type)
    if handler is None:
        logger.info("Unhandled stripe event type: %s", event_type)
        return
    handler(event)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_checkout_session_completed(event: dict) -> None:
    session = event["data"]["object"]
    metadata = session.get("metadata") or {}
    payment_id = metadata.get("payment_id")
    if not payment_id:
        logger.warning(
            "checkout.session.completed without payment_id metadata: %s",
            session.get("id"),
        )
        return

    payment = Payment.objects.filter(id=payment_id).first()
    if payment is None:
        logger.warning("Payment %s not found for session %s", payment_id, session.get("id"))
        return

    if payment.status == PaymentStatus.SUCCEEDED:
        return  # idempotent

    payment_intent_id = session.get("payment_intent") or None
    if payment_intent_id:
        payment.payment_intent_id = payment_intent_id

    payment.status = PaymentStatus.SUCCEEDED
    payment.save(update_fields=["payment_intent_id", "status", "updated_at"])

    order = Order.objects.filter(id=payment.order_id).first()
    if order is None:
        return

    try:
        mark_order_paid(order=order, actor=None, reason="stripe_checkout_completed")
    except InvalidOrderState as exc:
        # Late payment — order was cancelled/expired before webhook arrived.
        log_action(
            action="payment.late_payment",
            actor=None,
            target_type="order",
            target_id=order.id,
            metadata={
                "payment_id": str(payment.id),
                "order_status": exc.status,
                "stripe_session_id": session.get("id"),
            },
        )
        logger.warning(
            "Late payment for order %s (status %s), payment %s",
            order.id,
            exc.status,
            payment.id,
        )
        # Phase 8: trigger automatic refund from here.


def _handle_payment_intent_succeeded(event: dict) -> None:
    """Idempotent fallback — some Stripe flows emit this instead of the
    session-completed event. No-op if the payment is already SUCCEEDED."""
    intent = event["data"]["object"]
    payment_intent_id = intent.get("id")
    if not payment_intent_id:
        return

    payment = Payment.objects.filter(payment_intent_id=payment_intent_id).first()
    if payment is None:
        # Attempt to link via metadata order_id, but that is Phase 6.5 refinement.
        return
    if payment.status == PaymentStatus.SUCCEEDED:
        return

    payment.status = PaymentStatus.SUCCEEDED
    payment.save(update_fields=["status", "updated_at"])


def _handle_payment_intent_failed(event: dict) -> None:
    intent = event["data"]["object"]
    payment_intent_id = intent.get("id")
    if not payment_intent_id:
        return

    payment = Payment.objects.filter(payment_intent_id=payment_intent_id).first()
    if payment is None:
        return
    if payment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED):
        return

    payment.status = PaymentStatus.FAILED
    payment.save(update_fields=["status", "updated_at"])


def _handle_charge_refunded(event: dict) -> None:
    """
    Record Stripe-initiated or admin-initiated refunds.

    Phase 6 only updates Payment status; Order-level refund state and the
    Refund row creation happen in the Phase 6 admin refund flow (Blok 3).
    """
    charge = event["data"]["object"]
    payment_intent_id = charge.get("payment_intent")
    if not payment_intent_id:
        return

    payment = Payment.objects.filter(payment_intent_id=payment_intent_id).first()
    if payment is None:
        return

    amount_refunded = int(charge.get("amount_refunded") or 0)
    if amount_refunded <= 0:
        return

    new_status = (
        PaymentStatus.REFUNDED
        if amount_refunded >= payment.amount_cents
        else PaymentStatus.PARTIALLY_REFUNDED
    )
    if payment.status != new_status:
        payment.status = new_status
        payment.save(update_fields=["status", "updated_at"])


_HANDLERS = {
    "checkout.session.completed": _handle_checkout_session_completed,
    "payment_intent.succeeded": _handle_payment_intent_succeeded,
    "payment_intent.payment_failed": _handle_payment_intent_failed,
    "charge.refunded": _handle_charge_refunded,
}
