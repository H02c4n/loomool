import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.payments.models import (
    Payment,
    PaymentEvent,
    PaymentStatus,
    Refund,
    RefundStatus,
)
from apps.shop.models import Cart, CartItem
from apps.shop.services import create_order_from_cart
from apps.stores.models import Store

User = get_user_model()


@pytest.fixture
def order(db):
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
    return create_order_from_cart(cart=cart, user=buyer)


@pytest.mark.django_db
class TestPaymentModel:
    def test_create_payment(self, order):
        p = Payment.objects.create(
            order=order,
            checkout_session_id="cs_test_abc",
            amount_cents=order.total_cents,
            currency=order.currency,
            status=PaymentStatus.CREATED,
        )
        assert p.id is not None
        assert p.payment_intent_id is None
        assert p.status == PaymentStatus.CREATED

    def test_amount_must_be_positive(self, order):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(
                    order=order,
                    checkout_session_id="cs_test_zero",
                    amount_cents=0,
                    currency="SEK",
                )

    def test_checkout_session_id_unique(self, order):
        Payment.objects.create(
            order=order,
            checkout_session_id="cs_test_dup",
            amount_cents=100,
            currency="SEK",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(
                    order=order,
                    checkout_session_id="cs_test_dup",
                    amount_cents=100,
                    currency="SEK",
                )

    def test_payment_intent_id_unique_when_set(self, order):
        Payment.objects.create(
            order=order,
            checkout_session_id="cs_1",
            payment_intent_id="pi_abc",
            amount_cents=100,
            currency="SEK",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(
                    order=order,
                    checkout_session_id="cs_2",
                    payment_intent_id="pi_abc",
                    amount_cents=100,
                    currency="SEK",
                )

    def test_multiple_payments_allowed_per_order(self, order):
        Payment.objects.create(
            order=order,
            checkout_session_id="cs_1",
            amount_cents=100,
            currency="SEK",
            status=PaymentStatus.FAILED,
        )
        Payment.objects.create(
            order=order,
            checkout_session_id="cs_2",
            amount_cents=100,
            currency="SEK",
            status=PaymentStatus.CREATED,
        )
        assert Payment.objects.filter(order=order).count() == 2


@pytest.mark.django_db
class TestPaymentEventModel:
    def test_stripe_event_id_unique(self):
        PaymentEvent.objects.create(
            stripe_event_id="evt_1",
            event_type="checkout.session.completed",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PaymentEvent.objects.create(
                    stripe_event_id="evt_1",
                    event_type="checkout.session.completed",
                )

    def test_processed_at_nullable(self):
        e = PaymentEvent.objects.create(
            stripe_event_id="evt_2",
            event_type="checkout.session.completed",
        )
        assert e.processed_at is None

    def test_can_set_processed_at(self):
        e = PaymentEvent.objects.create(
            stripe_event_id="evt_3",
            event_type="checkout.session.completed",
        )
        e.processed_at = timezone.now()
        e.save(update_fields=["processed_at"])
        e.refresh_from_db()
        assert e.processed_at is not None


@pytest.mark.django_db
class TestRefundModel:
    def _make_payment(self, order):
        return Payment.objects.create(
            order=order,
            checkout_session_id="cs_ref",
            payment_intent_id="pi_ref",
            amount_cents=order.total_cents,
            currency=order.currency,
            status=PaymentStatus.SUCCEEDED,
        )

    def test_create_refund(self, order):
        payment = self._make_payment(order)
        r = Refund.objects.create(
            payment=payment,
            stripe_refund_id="re_1",
            amount_cents=payment.amount_cents,
            status=RefundStatus.PENDING,
        )
        assert r.id is not None

    def test_refund_exceeds_payment_rejected(self, order):
        payment = self._make_payment(order)
        r = Refund(
            payment=payment,
            stripe_refund_id="re_2",
            amount_cents=payment.amount_cents + 1,
        )
        with pytest.raises(ValidationError):
            r.save()

    def test_refund_amount_positive(self, order):
        payment = self._make_payment(order)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Refund.objects.create(
                    payment=payment,
                    stripe_refund_id="re_3",
                    amount_cents=0,
                )
