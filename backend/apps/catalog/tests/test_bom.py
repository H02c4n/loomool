import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import (
    Category,
    Product,
    ProductComponent,
    ProductType,
    ProductVariant,
)
from apps.stores.models import Store

User = get_user_model()


def _setup_two_products():
    seller = User.objects.create_user(email="s@x.com", password="long-password-123")
    store = Store.objects.create(name="Loom", slug="loom", owner=seller)
    cat = Category.objects.create(name="K", slug="k")

    kit_product = Product.objects.create(
        store=store,
        type=ProductType.DIY_KIT,
        category=cat,
        name="Bag kit",
        slug="bag-kit",
        base_price_cents=100,
    )
    kit_variant = ProductVariant.objects.create(product=kit_product, sku="KIT-1")

    yarn_product = Product.objects.create(
        store=store,
        type=ProductType.MATERIAL,
        category=cat,
        name="Yarn",
        slug="yarn",
        base_price_cents=50,
    )
    yarn_variant = ProductVariant.objects.create(product=yarn_product, sku="Y-1")

    return seller, store, kit_variant, yarn_variant


@pytest.mark.django_db
class TestBOMService:
    def test_add_valid_component(self):
        seller, _, kit_v, yarn_v = _setup_two_products()
        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:bom-list-add", args=[kit_v.id]),
            {"component_variant_id": str(yarn_v.id), "quantity": 3},
            format="json",
        )
        assert r.status_code == 201, r.content
        assert ProductComponent.objects.count() == 1
        assert ProductComponent.objects.get().quantity == 3

    def test_reject_kit_containing_kit(self):
        seller, store, kit_v, _ = _setup_two_products()
        cat = Category.objects.get(slug="k")
        other_kit = Product.objects.create(
            store=store,
            type=ProductType.DIY_KIT,
            category=cat,
            name="Other kit",
            slug="other-kit",
            base_price_cents=100,
        )
        other_kit_v = ProductVariant.objects.create(product=other_kit, sku="KIT-2")

        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:bom-list-add", args=[kit_v.id]),
            {"component_variant_id": str(other_kit_v.id), "quantity": 1},
            format="json",
        )
        assert r.status_code == 400
        assert "component_variant" in r.json()

    def test_kit_containing_non_kit_rejected_as_kit(self):
        seller, store, _, yarn_v = _setup_two_products()
        c = APIClient()
        c.force_authenticate(user=seller)
        # yarn_v is a MATERIAL; using it as the "kit" side should 400
        r = c.post(
            reverse("catalog:bom-list-add", args=[yarn_v.id]),
            {"component_variant_id": str(yarn_v.id), "quantity": 1},
            format="json",
        )
        assert r.status_code == 400

    def test_cross_store_component_rejected(self):
        seller, _, kit_v, _ = _setup_two_products()
        other_seller = User.objects.create_user(email="o@x.com", password="long-password-123")
        other_store = Store.objects.create(name="Other", slug="other", owner=other_seller)
        cat = Category.objects.get(slug="k")
        other_yarn_product = Product.objects.create(
            store=other_store,
            type=ProductType.MATERIAL,
            category=cat,
            name="Foreign yarn",
            slug="foreign-yarn",
            base_price_cents=50,
        )
        other_yarn_v = ProductVariant.objects.create(product=other_yarn_product, sku="FY-1")

        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:bom-list-add", args=[kit_v.id]),
            {"component_variant_id": str(other_yarn_v.id), "quantity": 1},
            format="json",
        )
        assert r.status_code == 400
        assert "component_variant" in r.json()

    def test_upsert_updates_quantity(self):
        seller, _, kit_v, yarn_v = _setup_two_products()
        c = APIClient()
        c.force_authenticate(user=seller)
        c.post(
            reverse("catalog:bom-list-add", args=[kit_v.id]),
            {"component_variant_id": str(yarn_v.id), "quantity": 2},
            format="json",
        )
        c.post(
            reverse("catalog:bom-list-add", args=[kit_v.id]),
            {"component_variant_id": str(yarn_v.id), "quantity": 5},
            format="json",
        )
        assert ProductComponent.objects.get().quantity == 5


@pytest.mark.django_db
class TestBOMIsolation:
    def test_other_seller_cannot_add(self):
        _, _, kit_v, yarn_v = _setup_two_products()
        other = User.objects.create_user(email="o@x.com", password="long-password-123")
        c = APIClient()
        c.force_authenticate(user=other)
        r = c.post(
            reverse("catalog:bom-list-add", args=[kit_v.id]),
            {"component_variant_id": str(yarn_v.id), "quantity": 1},
            format="json",
        )
        assert r.status_code == 404
        assert ProductComponent.objects.count() == 0

    def test_other_seller_cannot_list(self):
        _, _, kit_v, _ = _setup_two_products()
        other = User.objects.create_user(email="o@x.com", password="long-password-123")
        c = APIClient()
        c.force_authenticate(user=other)
        r = c.get(reverse("catalog:bom-list-add", args=[kit_v.id]))
        assert r.status_code == 404
