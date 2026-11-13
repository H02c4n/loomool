import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import (
    Category,
    Product,
    ProductRelationship,
    ProductType,
    RelationshipType,
)
from apps.stores.models import Store

User = get_user_model()


def _setup():
    seller = User.objects.create_user(email="s@x.com", password="long-password-123")
    store = Store.objects.create(name="Loom", slug="loom", owner=seller)
    cat = Category.objects.create(name="K", slug="k")
    finished = Product.objects.create(
        store=store,
        type=ProductType.FINISHED_HANDMADE,
        category=cat,
        name="Bag",
        slug="bag",
        base_price_cents=500,
    )
    kit = Product.objects.create(
        store=store,
        type=ProductType.DIY_KIT,
        category=cat,
        name="Bag kit",
        slug="bag-kit",
        base_price_cents=300,
    )
    return seller, finished, kit


@pytest.mark.django_db
class TestRelationships:
    def test_add_valid(self):
        seller, finished, kit = _setup()
        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:relationship-list-add", args=[finished.id]),
            {
                "to_product_id": str(kit.id),
                "relationship_type": RelationshipType.KIT_FOR,
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        assert ProductRelationship.objects.count() == 1

    def test_self_relationship_rejected(self):
        seller, finished, _ = _setup()
        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:relationship-list-add", args=[finished.id]),
            {
                "to_product_id": str(finished.id),
                "relationship_type": RelationshipType.RELATED,
            },
            format="json",
        )
        assert r.status_code == 400

    def test_list(self):
        seller, finished, kit = _setup()
        ProductRelationship.objects.create(
            from_product=finished,
            to_product=kit,
            relationship_type=RelationshipType.KIT_FOR,
        )
        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.get(reverse("catalog:relationship-list-add", args=[finished.id]))
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["relationship_type"] == "KIT_FOR"

    def test_cross_store_relationship_allowed(self):
        seller, finished, _ = _setup()
        other_seller = User.objects.create_user(email="o@x.com", password="long-password-123")
        other_store = Store.objects.create(name="Other", slug="other", owner=other_seller)
        cat = Category.objects.get(slug="k")
        other_product = Product.objects.create(
            store=other_store,
            type=ProductType.DIGITAL_PATTERN,
            category=cat,
            name="Pattern",
            slug="pattern",
            base_price_cents=50,
        )

        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:relationship-list-add", args=[finished.id]),
            {
                "to_product_id": str(other_product.id),
                "relationship_type": RelationshipType.PATTERN_FOR,
            },
            format="json",
        )
        assert r.status_code == 201

    def test_other_seller_cannot_add(self):
        _, finished, kit = _setup()
        other = User.objects.create_user(email="o@x.com", password="long-password-123")
        c = APIClient()
        c.force_authenticate(user=other)
        r = c.post(
            reverse("catalog:relationship-list-add", args=[finished.id]),
            {
                "to_product_id": str(kit.id),
                "relationship_type": RelationshipType.KIT_FOR,
            },
            format="json",
        )
        assert r.status_code == 404
        assert ProductRelationship.objects.count() == 0
