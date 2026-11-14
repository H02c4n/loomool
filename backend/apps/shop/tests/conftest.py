import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.catalog.models import (
    Category,
    Product,
    ProductImage,
    ProductType,
    ProductVariant,
)
from apps.inventory.models import Inventory
from apps.stores.models import Store

User = get_user_model()


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def seller(db):
    return User.objects.create_user(email="seller@example.com", password="long-password-123")


@pytest.fixture
def store(db, seller):
    return Store.objects.create(name="Loom", slug="loom", owner=seller)


@pytest.fixture
def category_root(db):
    return Category.objects.create(name="Örgü", slug="orgu")


@pytest.fixture
def category_child(db, category_root):
    return Category.objects.create(name="Kitler", slug="kitler", parent=category_root)


@pytest.fixture
def category_sibling(db, category_root):
    return Category.objects.create(name="İpler", slug="ipler", parent=category_root)


def _make_product(
    *,
    store,
    category,
    name,
    slug,
    type=ProductType.DIY_KIT,
    price_cents=10000,
    is_active=True,
    stock=10,
    with_image=False,
):
    product = Product.objects.create(
        store=store,
        category=category,
        type=type,
        name=name,
        slug=slug,
        base_price_cents=price_cents,
        is_active=is_active,
    )
    variant = ProductVariant.objects.create(product=product, sku=f"{slug}-1")
    Inventory.objects.create(variant=variant, quantity_available=stock, quantity_reserved=0)
    if with_image:
        key_base = f"products/{product.id}/x"
        for suffix in ("_original.webp", "_medium.webp", "_thumb.webp"):
            default_storage.save(f"{key_base}{suffix}", ContentFile(b"fake"))
        ProductImage.objects.create(
            product=product,
            storage_key_original=f"{key_base}_original.webp",
            storage_key_medium=f"{key_base}_medium.webp",
            storage_key_thumb=f"{key_base}_thumb.webp",
            width=100,
            height=100,
            byte_size=4,
            alt_text="",
        )
    return product


@pytest.fixture
def product_factory():
    return _make_product
