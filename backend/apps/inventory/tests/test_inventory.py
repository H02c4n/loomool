import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.catalog.models import Category, Product, ProductType, ProductVariant
from apps.inventory.models import Inventory
from apps.inventory.services import (
    InsufficientStock,
    adjust,
    consume,
    release,
    reserve,
)
from apps.stores.models import Store

User = get_user_model()


@pytest.fixture
def variant(db):
    seller = User.objects.create_user(email="s@x.com", password="long-password-123")
    store = Store.objects.create(name="L", slug="l", owner=seller)
    cat = Category.objects.create(name="K", slug="k")
    product = Product.objects.create(
        store=store,
        type=ProductType.DIY_KIT,
        category=cat,
        name="P",
        slug="p",
        base_price_cents=100,
    )
    v = ProductVariant.objects.create(product=product, sku="SKU-1")
    Inventory.objects.create(variant=v, quantity_available=10, quantity_reserved=0)
    return v


@pytest.mark.django_db
class TestInventoryReservation:
    def test_reserve(self, variant):
        inv = reserve(variant.id, 3)
        assert inv.quantity_available == 7
        assert inv.quantity_reserved == 3

    def test_reserve_insufficient(self, variant):
        with pytest.raises(InsufficientStock):
            reserve(variant.id, 11)

    def test_release(self, variant):
        reserve(variant.id, 3)
        inv = release(variant.id, 2)
        assert inv.quantity_available == 9
        assert inv.quantity_reserved == 1

    def test_consume(self, variant):
        reserve(variant.id, 3)
        inv = consume(variant.id, 2)
        assert inv.quantity_available == 7
        assert inv.quantity_reserved == 1

    def test_adjust(self, variant):
        inv = adjust(variant.id, 20)
        assert inv.quantity_available == 20

    def test_check_constraint_negative(self, variant):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Inventory.objects.filter(variant=variant).update(quantity_available=-1)
