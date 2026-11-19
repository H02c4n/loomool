from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.shop.models import Cart, CartItem, OrderStatus
from apps.shop.services import create_order_from_cart
from apps.shop.tasks import expire_stale_orders_task
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
    buyer = User.objects.create_user(email="b@x.com", password="long-password-123")
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, variant=variant, quantity=2)
    order = create_order_from_cart(cart=cart, user=buyer)
    return {"order": order, "variant": variant}


@pytest.mark.django_db
class TestOrderExpiry:
    def test_expired_order_cancelled(self, setup):
        # Fast-forward: make order already expired.
        setup["order"].expires_at = timezone.now() - timedelta(minutes=1)
        setup["order"].save(update_fields=["expires_at"])

        result = expire_stale_orders_task()
        assert result["expired"] == 1
        assert result["skipped"] == 0

        setup["order"].refresh_from_db()
        assert setup["order"].status == OrderStatus.CANCELLED

        inv = Inventory.objects.get(variant=setup["variant"])
        assert inv.quantity_available == 10
        assert inv.quantity_reserved == 0

    def test_non_expired_not_touched(self, setup):
        result = expire_stale_orders_task()
        assert result["expired"] == 0
        setup["order"].refresh_from_db()
        assert setup["order"].status == OrderStatus.PENDING_PAYMENT

    def test_already_cancelled_skipped(self, setup):
        setup["order"].status = OrderStatus.CANCELLED
        setup["order"].save(update_fields=["status"])
        setup["order"].expires_at = timezone.now() - timedelta(minutes=1)
        setup["order"].save(update_fields=["expires_at"])

        result = expire_stale_orders_task()
        # Already cancelled -> not a candidate (filter on PENDING_PAYMENT).
        assert result["expired"] == 0
