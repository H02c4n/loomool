import logging

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.csrf import enforce_csrf as _enforce_csrf
from apps.payments import services, stripe_client, webhook_handlers
from apps.payments.api.serializers import CreateCheckoutSerializer
from apps.payments.models import PaymentEvent
from apps.shop.models import Order
from apps.shop.services import InvalidOrderState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers (duplicated from shop.views for isolation; refactor in Phase 7)
# ---------------------------------------------------------------------------


def _limited(request) -> bool:
    return getattr(request._request, "limited", False)


def _too_many() -> Response:
    return Response(
        {"detail": "Too many requests. Please try again later."},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


def _minimise_payload(event: dict) -> dict:
    """Store only IDs and statuses — never card data, never PII."""
    obj = (event.get("data") or {}).get("object") or {}
    return {
        "id": event.get("id"),
        "type": event.get("type"),
        "created": event.get("created"),
        "data": {
            "object": {
                "id": obj.get("id"),
                "status": obj.get("status"),
                "amount_total": obj.get("amount_total") or obj.get("amount"),
                "amount_refunded": obj.get("amount_refunded"),
                "currency": obj.get("currency"),
                "payment_intent": obj.get("payment_intent"),
                "metadata": obj.get("metadata") or {},
            }
        },
    }


# ---------------------------------------------------------------------------
# Checkout session
# ---------------------------------------------------------------------------


@ratelimit(key="user", rate="5/m", method="POST", block=False)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session_view(request):
    if (err := _enforce_csrf(request._request)) is not None:
        return err
    if _limited(request):
        return _too_many()

    serializer = CreateCheckoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    order = Order.objects.filter(
        id=serializer.validated_data["order_id"],
        user=request.user,
    ).first()
    if order is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        payment, checkout_url = services.create_checkout_session(order=order, user=request.user)
    except services.OrderExpired:
        return Response({"detail": "order_expired"}, status=status.HTTP_400_BAD_REQUEST)
    except InvalidOrderState as exc:
        return Response(
            {"detail": "invalid_order_state", "current_status": exc.status},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "payment_id": str(payment.id),
            "session_id": payment.checkout_session_id,
            "checkout_url": checkout_url,
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def webhook_view(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured")
        return Response({"detail": "webhook_not_configured"}, status=500)

    try:
        event = stripe_client.webhook().construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return Response({"detail": "invalid_payload"}, status=400)
    except stripe.error.SignatureVerificationError:
        return Response({"detail": "invalid_signature"}, status=400)

    event_id = event["id"]
    event_type = event["type"]

    try:
        with transaction.atomic():
            pe, created = PaymentEvent.objects.get_or_create(
                stripe_event_id=event_id,
                defaults={
                    "event_type": event_type,
                    "payload": _minimise_payload(event),
                    "processed_at": None,
                    "signature_valid": True,
                },
            )
            if not created:
                # Already processed or in-flight — treat as idempotent no-op.
                return Response(status=status.HTTP_200_OK)

            webhook_handlers.handle_event(event)

            pe.processed_at = timezone.now()
            pe.save(update_fields=["processed_at"])
    except Exception as exc:
        logger.exception(
            "Webhook handler failed for event %s (%s): %s",
            event_id,
            event_type,
            exc,
        )
        return Response({"detail": "handler_failed"}, status=500)

    return Response(status=status.HTTP_200_OK)
