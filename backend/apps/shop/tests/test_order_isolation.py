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
        base_price_cents=100,
    )
    variant = ProductVariant.objects.create(product=product, sku="Y-1")
    Inventory.objects.create(variant=variant, quantity_available=10, quantity_reserved=0)
    buyer_a = User.objects.create_user(email="a@x.com", password="long-password-123")
    buyer_b = User.objects.create_user(email="b@x.com", password="long-password-123")
    cart_a = Cart.objects.create(user=buyer_a)
    CartItem.objects.create(cart=cart_a, variant=variant, quantity=1)
    order = create_order_from_cart(cart=cart_a, user=buyer_a)
    return {"order": order, "buyer_a": buyer_a, "buyer_b": buyer_b}


@pytest.mark.django_db
class TestOrderIsolation:
    def test_buyer_b_cannot_read_a_order(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer_b"])
        r = c.get(reverse("shop:order-detail", args=[setup["order"].id]))
        assert r.status_code == 404

    def test_buyer_b_cannot_cancel_a_order(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer_b"])
        r = c.post(reverse("shop:order-cancel", args=[setup["order"].id]))
        assert r.status_code == 404

    def test_buyer_b_list_does_not_include_a(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer_b"])
        r = c.get(reverse("shop:order-list"))
        assert r.status_code == 200
        assert r.json() == []
