import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.payments.models import Payment, PaymentEvent, PaymentStatus
from apps.shop.models import Cart, CartItem, OrderStatus
from apps.shop.services import create_order_from_cart
from apps.stores.models import Store

User = get_user_model()
WEBHOOK_URL = "/api/v1/payments/webhook/"


@pytest.fixture
def order_with_payment(db):
    seller = User.objects.create_user(email="s@x.com", password="long-password-123")
    store = Store.objects.create(name="L", slug="l", owner=seller)
    cat = Category.objects.create(name="K", slug="k")
    product = Product.objects.create(
        store=store,
        category=cat,
        type=ProductType.MATERIAL,
        name="Yarn",
        slug="yarn",
        base_price_cents=500,
    )
    variant = ProductVariant.objects.create(product=product, sku="Y-1")
    Inventory.objects.create(variant=variant, quantity_available=10, quantity_reserved=0)
    buyer = User.objects.create_user(email="b@x.com", password="long-password-123")
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, variant=variant, quantity=2)
    order = create_order_from_cart(cart=cart, user=buyer)

    payment = Payment.objects.create(
        order=order,
        checkout_session_id="cs_test_wh",
        amount_cents=order.total_cents,
        currency=order.currency,
        status=PaymentStatus.CREATED,
    )
    return order, payment


def _session_event(event_id, payment, payment_intent="pi_test_123"):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "created": 1700000000,
        "data": {
            "object": {
                "id": payment.checkout_session_id,
                "status": "complete",
                "amount_total": payment.amount_cents,
                "currency": payment.currency.lower(),
                "payment_intent": payment_intent,
                "metadata": {
                    "payment_id": str(payment.id),
                    "order_id": str(payment.order_id),
                },
            }
        },
    }


@pytest.fixture
def mock_construct_valid_signature():
    """Bypass signature verification; return whatever event we feed."""

    def _factory(event):
        def fake_construct(payload, sig_header, secret):
            return event

        return patch(
            "apps.payments.api.views.stripe_client.webhook",
            return_value=MagicMock(construct_event=fake_construct),
        )

    return _factory


@pytest.mark.django_db
class TestWebhook:
    def test_session_completed_transitions_to_paid(
        self, order_with_payment, mock_construct_valid_signature
    ):
        order, payment = order_with_payment
        event = _session_event("evt_test_1", payment)

        with mock_construct_valid_signature(event):
            r = APIClient().post(
                WEBHOOK_URL, data=json.dumps(event), content_type="application/json"
            )

        assert r.status_code == 200
        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.status == OrderStatus.PAID
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.payment_intent_id == "pi_test_123"
        assert PaymentEvent.objects.filter(stripe_event_id="evt_test_1").exists()

    def test_duplicate_event_id_is_idempotent(
        self, order_with_payment, mock_construct_valid_signature
    ):
        order, payment = order_with_payment
        event = _session_event("evt_test_dup", payment)

        with mock_construct_valid_signature(event):
            r1 = APIClient().post(
                WEBHOOK_URL, data=json.dumps(event), content_type="application/json"
            )
            r2 = APIClient().post(
                WEBHOOK_URL, data=json.dumps(event), content_type="application/json"
            )

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert PaymentEvent.objects.filter(stripe_event_id="evt_test_dup").count() == 1
        assert order.payments.first().status == PaymentStatus.SUCCEEDED

    def test_invalid_signature_returns_400(self, order_with_payment):
        import stripe

        with patch(
            "apps.payments.api.views.stripe_client.webhook",
        ) as mock_webhook:
            mock_webhook.return_value = MagicMock(
                construct_event=MagicMock(
                    side_effect=stripe.error.SignatureVerificationError("bad signature", "sig")
                )
            )
            r = APIClient().post(WEBHOOK_URL, data=b"{}", content_type="application/json")
        assert r.status_code == 400
        assert r.json()["detail"] == "invalid_signature"

    def test_late_payment_logs_without_transition(
        self, order_with_payment, mock_construct_valid_signature
    ):
        order, payment = order_with_payment
        order.status = OrderStatus.CANCELLED
        order.save(update_fields=["status"])

        event = _session_event("evt_test_late", payment)
        with mock_construct_valid_signature(event):
            r = APIClient().post(
                WEBHOOK_URL, data=json.dumps(event), content_type="application/json"
            )

        assert r.status_code == 200
        order.refresh_from_db()
        payment.refresh_from_db()
        # Order stays cancelled; payment is marked succeeded (money came in).
        assert order.status == OrderStatus.CANCELLED
        assert payment.status == PaymentStatus.SUCCEEDED

    def test_unknown_event_type_noop(self, order_with_payment, mock_construct_valid_signature):
        _, payment = order_with_payment
        event = {
            "id": "evt_test_unknown",
            "type": "customer.created",
            "created": 1700000000,
            "data": {"object": {"id": "cus_x"}},
        }
        with mock_construct_valid_signature(event):
            r = APIClient().post(
                WEBHOOK_URL, data=json.dumps(event), content_type="application/json"
            )
        assert r.status_code == 200
        assert PaymentEvent.objects.filter(stripe_event_id="evt_test_unknown").exists()

    def test_payment_intent_failed_marks_payment_failed(
        self, order_with_payment, mock_construct_valid_signature
    ):
        _, payment = order_with_payment
        payment.payment_intent_id = "pi_fail_1"
        payment.save(update_fields=["payment_intent_id"])

        event = {
            "id": "evt_test_fail",
            "type": "payment_intent.payment_failed",
            "created": 1700000000,
            "data": {"object": {"id": "pi_fail_1", "status": "requires_payment_method"}},
        }
        with mock_construct_valid_signature(event):
            r = APIClient().post(
                WEBHOOK_URL, data=json.dumps(event), content_type="application/json"
            )
        assert r.status_code == 200
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.FAILED
