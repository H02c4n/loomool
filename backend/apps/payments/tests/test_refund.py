from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.payments.models import (
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
)
from apps.payments.services import (
    AlreadyRefunded,
    PaymentNotRefundable,
    StripeRefundError,
    refund_payment,
)
from apps.shop.models import Cart, CartItem
from apps.shop.services import create_order_from_cart
from apps.stores.models import Store

User = get_user_model()


@pytest.fixture
def paid_payment(db):
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

    return Payment.objects.create(
        order=order,
        checkout_session_id="cs_test_refund",
        payment_intent_id="pi_test_refund",
        amount_cents=order.total_cents,
        currency=order.currency,
        status=PaymentStatus.SUCCEEDED,
    )


def _admin():
    return User.objects.create_user(email="admin@x.com", password="long-password-123")


@pytest.mark.django_db
class TestRefundService:
    @patch("apps.payments.services.stripe_client.client")
    def test_happy_path(self, mock_client_fn, paid_payment):
        mock_sdk = MagicMock()
        mock_refund = MagicMock()
        mock_refund.id = "re_test_1"
        mock_sdk.Refund.create.return_value = mock_refund
        mock_client_fn.return_value = mock_sdk

        admin = _admin()
        refund = refund_payment(payment=paid_payment, actor=admin, reason="test")

        assert refund.stripe_refund_id == "re_test_1"
        assert refund.amount_cents == paid_payment.amount_cents
        assert refund.status == RefundStatus.PENDING
        assert Refund.objects.filter(payment=paid_payment).count() == 1

        # The Stripe call must be made with the right arguments.
        mock_sdk.Refund.create.assert_called_once()
        call_kwargs = mock_sdk.Refund.create.call_args.kwargs
        assert call_kwargs["payment_intent"] == paid_payment.payment_intent_id
        assert call_kwargs["idempotency_key"] == f"refund-{paid_payment.id}"

    @patch("apps.payments.services.stripe_client.client")
    def test_not_refundable_when_not_succeeded(self, mock_client_fn, paid_payment):
        paid_payment.status = PaymentStatus.FAILED
        paid_payment.save(update_fields=["status"])

        with pytest.raises(PaymentNotRefundable) as exc:
            refund_payment(payment=paid_payment, actor=_admin(), reason="test")
        assert exc.value.status == "FAILED"

    @patch("apps.payments.services.stripe_client.client")
    def test_already_refunded(self, mock_client_fn, paid_payment):
        # Pre-existing successful refund
        Refund.objects.create(
            payment=paid_payment,
            stripe_refund_id="re_existing",
            amount_cents=paid_payment.amount_cents,
            status=RefundStatus.SUCCEEDED,
        )

        with pytest.raises(AlreadyRefunded):
            refund_payment(payment=paid_payment, actor=_admin(), reason="test")

    @patch("apps.payments.services.stripe_client.client")
    def test_missing_payment_intent(self, mock_client_fn, paid_payment):
        paid_payment.payment_intent_id = None
        paid_payment.save(update_fields=["payment_intent_id"])

        with pytest.raises(StripeRefundError) as exc:
            refund_payment(payment=paid_payment, actor=_admin(), reason="test")
        assert "missing_payment_intent" in str(exc.value)
