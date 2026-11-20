from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.shop.models import Cart, CartItem
from apps.shop.services import create_order_from_cart
from apps.stores.models import Store

User = get_user_model()


@pytest.fixture
def setup(db):
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
    buyer_a = User.objects.create_user(email="a@x.com", password="long-password-123")
    buyer_b = User.objects.create_user(email="b@x.com", password="long-password-123")
    cart = Cart.objects.create(user=buyer_a)
    CartItem.objects.create(cart=cart, variant=variant, quantity=1)
    order = create_order_from_cart(cart=cart, user=buyer_a)
    return {"order": order, "buyer_a": buyer_a, "buyer_b": buyer_b}


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


@pytest.mark.django_db
class TestCheckoutIsolation:
    @patch("apps.payments.services.stripe_client.client")
    def test_buyer_b_cannot_checkout_a_order(self, mock_client_fn, csrf_client, setup):
        mock_sdk = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "cs_test"
        mock_session.url = "https://checkout.stripe.com/x"
        mock_sdk.checkout.Session.create.return_value = mock_session
        mock_client_fn.return_value = mock_sdk

        csrf_client.force_authenticate(user=setup["buyer_b"])
        r = csrf_client.post(
            reverse("payments:checkout-session-create"),
            {"order_id": str(setup["order"].id)},
            format="json",
        )
        assert r.status_code == 404
