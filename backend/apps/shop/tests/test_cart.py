import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import (
    Product,
    ProductType,
    ProductVariant,
)
from apps.inventory.models import Inventory
from apps.shop.models import Cart, CartItem
from apps.stores.models import Store

User = get_user_model()


def _make_product(store, category, name, slug, price_cents=1000, stock=10):
    p = Product.objects.create(
        store=store,
        category=category,
        type=ProductType.DIY_KIT,
        name=name,
        slug=slug,
        base_price_cents=price_cents,
    )
    v = ProductVariant.objects.create(product=p, sku=f"{slug}-1")
    Inventory.objects.create(variant=v, quantity_available=stock, quantity_reserved=0)
    return p, v


@pytest.fixture
def csrf_client():
    """APIClient with CSRF cookie primed; sets X-CSRFToken on unsafe requests."""
    c = APIClient(enforce_csrf_checks=True)
    c.get(reverse("auth:csrf"))
    token = c.cookies["csrftoken"].value

    def _with_token(method_name):
        original = getattr(c, method_name)

        def wrapper(*args, **kwargs):
            kwargs.setdefault("HTTP_X_CSRFTOKEN", token)
            return original(*args, **kwargs)

        return wrapper

    for name in ("post", "patch", "put", "delete"):
        setattr(c, name, _with_token(name))

    return c


@pytest.mark.django_db
class TestAnonymousCart:
    def test_empty_cart_for_fresh_visitor(self, csrf_client):
        r = csrf_client.get(reverse("shop:cart"))
        assert r.status_code == 200
        assert r.json()["id"] is None
        assert r.json()["total_items"] == 0

    def test_add_item_creates_cart_and_cookie(self, csrf_client, store, category_child):
        _, variant = _make_product(store, category_child, "Bag", "bag")
        r = csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 2},
            format="json",
        )
        assert r.status_code == 201
        body = r.json()
        assert body["total_items"] == 2
        assert "cart_session" in r.cookies
        assert Cart.objects.count() == 1

    def test_add_same_variant_increments(self, csrf_client, store, category_child):
        _, variant = _make_product(store, category_child, "Bag", "bag")
        csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 2},
            format="json",
        )
        r = csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 3},
            format="json",
        )
        assert r.json()["total_items"] == 5
        assert CartItem.objects.get().quantity == 5

    def test_quantity_capped_at_10(self, csrf_client, store, category_child):
        _, variant = _make_product(store, category_child, "Bag", "bag")
        csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 8},
            format="json",
        )
        r = csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 5},
            format="json",
        )
        assert r.json()["total_items"] == 10

    def test_update_quantity(self, csrf_client, store, category_child):
        _, variant = _make_product(store, category_child, "Bag", "bag")
        csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 2},
            format="json",
        )
        item = CartItem.objects.get()
        r = csrf_client.patch(
            reverse("shop:cart-item", args=[item.id]),
            {"quantity": 7},
            format="json",
        )
        assert r.status_code == 200
        assert r.json()["total_items"] == 7

    def test_remove_item(self, csrf_client, store, category_child):
        _, variant = _make_product(store, category_child, "Bag", "bag")
        csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 2},
            format="json",
        )
        item = CartItem.objects.get()
        r = csrf_client.delete(reverse("shop:cart-item", args=[item.id]))
        assert r.status_code == 200
        assert r.json()["total_items"] == 0

    def test_inactive_variant_rejected(self, csrf_client, store, category_child):
        _, variant = _make_product(store, category_child, "Bag", "bag")
        variant.is_active = False
        variant.save()
        r = csrf_client.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 1},
            format="json",
        )
        assert r.status_code == 400
        assert CartItem.objects.count() == 0

    def test_csrf_required_for_anonymous_post(self, store, category_child):
        _, variant = _make_product(store, category_child, "Bag", "bag")
        # Client WITHOUT enforce_csrf_checks will bypass CSRF. Use one that
        # enforces, and don't prime the token.
        c = APIClient(enforce_csrf_checks=True)
        r = c.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 1},
            format="json",
        )
        assert r.status_code == 403


@pytest.mark.django_db
class TestAuthenticatedCart:
    def test_add_item_uses_user_cart(self, store, category_child):
        user = User.objects.create_user(email="u@x.com", password="long-password-123")
        _, variant = _make_product(store, category_child, "Bag", "bag")
        c = APIClient()
        c.force_authenticate(user=user)
        r = c.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 2},
            format="json",
        )
        assert r.status_code == 201
        assert Cart.objects.filter(user=user).exists()

    def test_authenticated_does_not_get_session_cookie(self, store, category_child):
        user = User.objects.create_user(email="u@x.com", password="long-password-123")
        _, variant = _make_product(store, category_child, "Bag", "bag")
        c = APIClient()
        c.force_authenticate(user=user)
        r = c.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(variant.id), "quantity": 1},
            format="json",
        )
        assert "cart_session" not in r.cookies

    def test_cart_groups_by_store(self, category_child):
        seller_a = User.objects.create_user(email="a@x.com", password="long-password-123")
        seller_b = User.objects.create_user(email="b@x.com", password="long-password-123")
        s_a = Store.objects.create(name="A", slug="a", owner=seller_a)
        s_b = Store.objects.create(name="B", slug="b", owner=seller_b)
        _, va = _make_product(s_a, category_child, "P1", "p1")
        _, vb = _make_product(s_b, category_child, "P2", "p2")

        buyer = User.objects.create_user(email="buyer@x.com", password="long-password-123")
        c = APIClient()
        c.force_authenticate(user=buyer)
        c.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(va.id), "quantity": 1},
            format="json",
        )
        r = c.post(
            reverse("shop:cart-add-item"),
            {"variant_id": str(vb.id), "quantity": 2},
            format="json",
        )
        body = r.json()
        assert len(body["store_groups"]) == 2
        assert body["total_items"] == 3
