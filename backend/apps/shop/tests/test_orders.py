import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.shop.models import (
    Cart,
    CartItem,
    Order,
    OrderStatus,
)
from apps.shop.services import create_order_from_cart
from apps.stores.models import Store

User = get_user_model()


def _buyer(email="buyer@example.com"):
    return User.objects.create_user(email=email, password="long-password-123")


def _seller_and_store(slug="loom"):
    seller = User.objects.create_user(
        email=f"seller-{slug}@example.com", password="long-password-123"
    )
    return seller, Store.objects.create(name=slug, slug=slug, owner=seller)


def _product(store, category, name, slug, price_cents=1000, stock=10, type_=None):
    p = Product.objects.create(
        store=store,
        category=category,
        type=type_ or ProductType.MATERIAL,
        name=name,
        slug=slug,
        base_price_cents=price_cents,
    )
    v = ProductVariant.objects.create(product=p, sku=f"{slug}-1")
    Inventory.objects.create(variant=v, quantity_available=stock, quantity_reserved=0)
    return p, v


@pytest.fixture
def setup(db):
    buyer = _buyer()
    seller, store = _seller_and_store()
    cat = Category.objects.create(name="K", slug="k")
    _, yarn = _product(store, cat, "Yarn", "yarn", price_cents=100, stock=10)

    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, variant=yarn, quantity=3)

    return {"buyer": buyer, "store": store, "cat": cat, "yarn": yarn, "cart": cart}


@pytest.mark.django_db
class TestOrderCreate:
    def test_create_from_cart(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.post(reverse("shop:order-list"))
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["status"] == OrderStatus.PENDING_PAYMENT
        assert body["total_cents"] == 300
        assert body["currency"] == "SEK"
        assert len(body["seller_orders"]) == 1
        assert len(body["seller_orders"][0]["items"]) == 1
        assert body["seller_orders"][0]["items"][0]["unit_price_cents"] == 100
        assert body["seller_orders"][0]["items"][0]["quantity"] == 3
        assert body["seller_orders"][0]["items"][0]["line_total_cents"] == 300

    def test_cart_cleared_after_order(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        c.post(reverse("shop:order-list"))
        assert setup["cart"].items.count() == 0

    def test_stock_reserved(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        c.post(reverse("shop:order-list"))
        inv = Inventory.objects.get(variant=setup["yarn"])
        assert inv.quantity_available == 7
        assert inv.quantity_reserved == 3

    def test_empty_cart_rejected(self, setup):
        setup["cart"].items.all().delete()
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.post(reverse("shop:order-list"))
        assert r.status_code == 400
        assert r.json()["detail"] == "cart_empty"

    def test_unauthenticated_rejected(self):
        c = APIClient()
        r = c.post(reverse("shop:order-list"))
        assert r.status_code in (401, 403)

    def test_out_of_stock_rolls_back(self, setup):
        Inventory.objects.filter(variant=setup["yarn"]).update(quantity_available=1)
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.post(reverse("shop:order-list"))
        assert r.status_code == 409
        assert r.json()["detail"] == "out_of_stock"
        # Rollback: stock unchanged, cart not cleared, no order created
        inv = Inventory.objects.get(variant=setup["yarn"])
        assert inv.quantity_available == 1
        assert inv.quantity_reserved == 0
        assert setup["cart"].items.count() == 1
        assert Order.objects.count() == 0

    def test_unsupported_product_type_rejected(self, setup):
        kit, kit_v = _product(
            setup["store"],
            setup["cat"],
            "Kit",
            "kit",
            price_cents=500,
            stock=5,
            type_=ProductType.DIY_KIT,
        )
        setup["cart"].items.all().delete()
        CartItem.objects.create(cart=setup["cart"], variant=kit_v, quantity=1)

        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.post(reverse("shop:order-list"))
        assert r.status_code == 400
        assert r.json()["detail"] == "unsupported_product_type"
        assert r.json()["product_type"] == "DIY_KIT"
        assert Order.objects.count() == 0

    def test_multi_seller_split(self, setup):
        seller_b = User.objects.create_user(
            email="seller-b@example.com", password="long-password-123"
        )
        store_b = Store.objects.create(name="B", slug="b", owner=seller_b)
        _, mat_b = _product(
            store_b,
            setup["cat"],
            "Thread",
            "thread",
            price_cents=50,
            stock=5,
        )
        CartItem.objects.create(cart=setup["cart"], variant=mat_b, quantity=2)

        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.post(reverse("shop:order-list"))
        assert r.status_code == 201
        body = r.json()
        assert len(body["seller_orders"]) == 2
        # 3 × 100 + 2 × 50 = 400
        assert body["total_cents"] == 400

        order = Order.objects.get(id=body["id"])
        assert order.seller_orders.count() == 2


@pytest.mark.django_db
class TestOrderDetail:
    def test_owner_sees_order(self, setup):
        order = create_order_from_cart(cart=setup["cart"], user=setup["buyer"])
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.get(reverse("shop:order-detail", args=[order.id]))
        assert r.status_code == 200
        assert r.json()["id"] == str(order.id)

    def test_other_user_gets_404(self, setup):
        order = create_order_from_cart(cart=setup["cart"], user=setup["buyer"])
        other = _buyer("other@example.com")
        c = APIClient()
        c.force_authenticate(user=other)
        r = c.get(reverse("shop:order-detail", args=[order.id]))
        assert r.status_code == 404

    def test_unknown_id_404(self, setup):
        import uuid

        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.get(reverse("shop:order-detail", args=[uuid.uuid4()]))
        assert r.status_code == 404


@pytest.mark.django_db
class TestOrderCancel:
    def test_cancel_pending(self, setup):
        order = create_order_from_cart(cart=setup["cart"], user=setup["buyer"])
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.post(
            reverse("shop:order-cancel", args=[order.id]),
            {"reason": "changed my mind"},
            format="json",
        )
        assert r.status_code == 200
        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED
        inv = Inventory.objects.get(variant=setup["yarn"])
        assert inv.quantity_available == 10
        assert inv.quantity_reserved == 0

    def test_cancel_twice_fails(self, setup):
        order = create_order_from_cart(cart=setup["cart"], user=setup["buyer"])
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        c.post(reverse("shop:order-cancel", args=[order.id]))
        r = c.post(reverse("shop:order-cancel", args=[order.id]))
        assert r.status_code == 400
        assert r.json()["detail"] == "invalid_order_state"

    def test_cancel_other_user_404(self, setup):
        order = create_order_from_cart(cart=setup["cart"], user=setup["buyer"])
        other = _buyer("other@example.com")
        c = APIClient()
        c.force_authenticate(user=other)
        r = c.post(reverse("shop:order-cancel", args=[order.id]))
        assert r.status_code == 404


@pytest.mark.django_db
class TestOrderList:
    def test_only_own_orders(self, setup):
        create_order_from_cart(cart=setup["cart"], user=setup["buyer"])
        other = _buyer("other@example.com")
        c = APIClient()
        c.force_authenticate(user=other)
        r = c.get(reverse("shop:order-list"))
        assert r.status_code == 200
        assert r.json() == []

    def test_own_orders_listed(self, setup):
        create_order_from_cart(cart=setup["cart"], user=setup["buyer"])
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.get(reverse("shop:order-list"))
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["total_cents"] == 300
