from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.payments.models import Payment, PaymentStatus
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


@pytest.fixture
def csrf_client():
    c = APIClient(enforce_csrf_checks=True)
    c.get(reverse("auth:csrf"))
    token = c.cookies["csrftoken"].value

    for name in ("post", "patch", "put", "delete"):
        original = getattr(c, name)

        def wrapper(*args, __orig=original, **kwargs):
            kwargs.setdefault("HTTP_X_CSRFTOKEN", token)
            return __orig(*args, **kwargs)

        setattr(c, name, wrapper)

    return c


def _mock_stripe_session_create(
    session_id="cs_test_new", url="https://checkout.stripe.com/pay/cs_test_new"
):
    mock_sdk = MagicMock()
    mock_session = MagicMock()
    mock_session.id = session_id
    mock_session.url = url
    mock_session.status = "open"
    mock_sdk.checkout.Session.create.return_value = mock_session
    mock_sdk.checkout.Session.retrieve.return_value = mock_session
    return mock_sdk


@pytest.mark.django_db
class TestCreateCheckoutSession:
    @patch("apps.payments.services.stripe_client.client")
    def test_happy_path(self, mock_client_fn, csrf_client, order):
        mock_client_fn.return_value = _mock_stripe_session_create()
        csrf_client.force_authenticate(user=order.user)

        r = csrf_client.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["session_id"] == "cs_test_new"
        assert body["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_new"
        assert Payment.objects.filter(order=order).count() == 1
        assert Payment.objects.get(order=order).status == PaymentStatus.CREATED

    def test_anonymous_rejected(self, order):
        c = APIClient()
        r = c.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r.status_code in (401, 403)

    def test_csrf_required(self, order):
        c = APIClient(enforce_csrf_checks=True)
        c.force_authenticate(user=order.user)
        r = c.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r.status_code == 403

    @patch("apps.payments.services.stripe_client.client")
    def test_other_user_order_404(self, mock_client_fn, csrf_client, order):
        mock_client_fn.return_value = _mock_stripe_session_create()
        other = User.objects.create_user(email="other@x.com", password="long-password-123")
        csrf_client.force_authenticate(user=other)
        r = csrf_client.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r.status_code == 404

    @patch("apps.payments.services.stripe_client.client")
    def test_non_pending_order_rejected(self, mock_client_fn, csrf_client, order):
        order.status = "CANCELLED"
        order.save(update_fields=["status"])
        mock_client_fn.return_value = _mock_stripe_session_create()
        csrf_client.force_authenticate(user=order.user)
        r = csrf_client.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "invalid_order_state"

    @patch("apps.payments.services.stripe_client.client")
    def test_expired_order_rejected(self, mock_client_fn, csrf_client, order):
        order.expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["expires_at"])
        csrf_client.force_authenticate(user=order.user)
        r = csrf_client.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "order_expired"

    @patch("apps.payments.services.stripe_client.client")
    def test_reuse_open_session(self, mock_client_fn, csrf_client, order):
        mock_sdk = _mock_stripe_session_create()
        mock_client_fn.return_value = mock_sdk
        csrf_client.force_authenticate(user=order.user)

        r1 = csrf_client.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r1.status_code == 201

        r2 = csrf_client.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(order.id)},
            format="json",
        )
        assert r2.status_code == 201
        # Only one Payment row.
        assert Payment.objects.filter(order=order).count() == 1
