import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.shop.models import Cart, CartItem
from apps.stores.models import Store

User = get_user_model()


@pytest.mark.django_db
class TestCartMerge:
    def test_session_cart_merges_into_user_cart(self):
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

        # Anonymous cart with 3 items.
        c = APIClient(enforce_csrf_checks=True)
        c.get(reverse("auth:csrf"))
        token = c.cookies["csrftoken"].value
        r = c.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 3},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        session_key = r.cookies["cart_session"].value
        assert Cart.objects.filter(session_key=session_key).exists()

        # Now log in (login triggers user_logged_in signal).
        buyer = User.objects.create_user(email="b@x.com", password="long-password-123")
        # Prime CSRF again for authenticated login
        c.get(reverse("auth:csrf"))
        token = c.cookies["csrftoken"].value
        r = c.post(
            reverse("auth:login"),
            {"email": buyer.email, "password": "long-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert r.status_code == 200

        # Session cart must be gone; user cart must have 3 items.
        assert not Cart.objects.filter(session_key=session_key).exists()
        user_cart = Cart.objects.get(user=buyer)
        assert user_cart.items.count() == 1
        assert user_cart.items.first().quantity == 3

    def test_merge_sums_existing_quantities(self):
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

        buyer = User.objects.create_user(email="b@x.com", password="long-password-123")

        # Pre-existing user cart with 4 of the same variant.
        user_cart, _ = Cart.objects.get_or_create(user=buyer)
        CartItem.objects.create(cart=user_cart, variant=variant, quantity=4)

        # Anonymous cart with 3 of the same variant.
        session_cart = Cart.objects.create(session_key="abc")
        CartItem.objects.create(cart=session_cart, variant=variant, quantity=3)

        # Merge.
        from apps.shop.services import merge_session_cart

        merge_session_cart(user=buyer, session_key="abc")

        assert not Cart.objects.filter(session_key="abc").exists()
        assert CartItem.objects.get(cart=user_cart).quantity == 7
