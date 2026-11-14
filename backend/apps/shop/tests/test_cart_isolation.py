import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.shop.models import CartItem
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
        type=ProductType.DIY_KIT,
        name="P",
        slug="p",
        base_price_cents=100,
    )
    variant = ProductVariant.objects.create(product=product, sku="P-1")
    Inventory.objects.create(variant=variant, quantity_available=10, quantity_reserved=0)

    buyer_a = User.objects.create_user(email="a@x.com", password="long-password-123")
    buyer_b = User.objects.create_user(email="b@x.com", password="long-password-123")

    ca = APIClient()
    ca.force_authenticate(user=buyer_a)
    r = ca.post(
        reverse("shop:cart-add-item"),
        {"variant_id": str(variant.id), "quantity": 1},
        format="json",
    )
    item_a_id = r.json()["store_groups"][0]["items"][0]["id"]

    return {"variant": variant, "buyer_a": buyer_a, "buyer_b": buyer_b, "item_a_id": item_a_id}


@pytest.mark.django_db
class TestCartIsolation:
    def test_buyer_b_cannot_patch_a_item(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer_b"])
        r = c.patch(
            reverse("shop:cart-item", args=[setup["item_a_id"]]),
            {"quantity": 5},
            format="json",
        )
        assert r.status_code == 404
        item = CartItem.objects.get(id=setup["item_a_id"])
        assert item.quantity == 1

    def test_buyer_b_cannot_delete_a_item(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer_b"])
        r = c.delete(reverse("shop:cart-item", args=[setup["item_a_id"]]))
        assert r.status_code == 404
        assert CartItem.objects.filter(id=setup["item_a_id"]).exists()

    def test_buyer_b_cart_does_not_show_a_items(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer_b"])
        r = c.get(reverse("shop:cart"))
        assert r.status_code == 200
        assert r.json()["total_items"] == 0

    def test_anonymous_cannot_see_user_cart(self, setup):
        # Fresh anonymous client, no cart_session cookie -> empty cart.
        c = APIClient()
        r = c.get(reverse("shop:cart"))
        assert r.status_code == 200
        assert r.json()["id"] is None
