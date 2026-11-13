import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import RoleChoices
from apps.catalog.models import (
    AttributeType,
    Category,
    CategoryAttributeDefinition,
    Product,
    ProductType,
)
from apps.stores.models import Store

User = get_user_model()


def _seller(email="seller@example.com"):
    return User.objects.create_user(email=email, password="long-password-123")


def _store(owner, name="Loom", slug="loom"):
    return Store.objects.create(name=name, slug=slug, owner=owner)


def _category(slug="kitler"):
    return Category.objects.create(name=slug.title(), slug=slug)


@pytest.mark.django_db
class TestProductCreate:
    def test_create_minimal_product(self):
        seller = _seller()
        store = _store(seller)
        cat = _category()

        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:product-list"),
            {
                "store_id": str(store.id),
                "type": ProductType.DIY_KIT,
                "category_id": str(cat.id),
                "name": "Knitted bag kit",
                "slug": "knitted-bag-kit",
                "base_price_cents": 29900,
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["name"] == "Knitted bag kit"
        assert body["store"] == str(store.id)
        assert body["currency"] == "SEK"
        assert Product.objects.count() == 1

    def test_create_rejects_store_not_owned(self):
        seller = _seller("a@x.com")
        other = _seller("b@x.com")
        other_store = _store(other, name="Other", slug="other")
        cat = _category()

        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:product-list"),
            {
                "store_id": str(other_store.id),
                "type": ProductType.DIY_KIT,
                "category_id": str(cat.id),
                "name": "X",
                "slug": "x",
                "base_price_cents": 100,
            },
            format="json",
        )
        assert r.status_code == 404
        assert Product.objects.count() == 0

    def test_create_rejects_unknown_category(self):
        seller = _seller()
        store = _store(seller)
        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:product-list"),
            {
                "store_id": str(store.id),
                "type": ProductType.DIY_KIT,
                "category_id": "00000000-0000-0000-0000-000000000000",
                "name": "X",
                "slug": "x",
                "base_price_cents": 100,
            },
            format="json",
        )
        assert r.status_code == 400

    def test_required_attribute_missing(self):
        seller = _seller()
        store = _store(seller)
        cat = _category()
        CategoryAttributeDefinition.objects.create(
            category=cat,
            key="yarn_type",
            label="Yarn type",
            type=AttributeType.TEXT,
            required=True,
        )

        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:product-list"),
            {
                "store_id": str(store.id),
                "type": ProductType.DIY_KIT,
                "category_id": str(cat.id),
                "name": "X",
                "slug": "x",
                "base_price_cents": 100,
                "attributes": {},
            },
            format="json",
        )
        assert r.status_code == 400
        assert "yarn_type" in r.json()

    def test_unknown_attribute_rejected(self):
        seller = _seller()
        store = _store(seller)
        cat = _category()

        c = APIClient()
        c.force_authenticate(user=seller)
        r = c.post(
            reverse("catalog:product-list"),
            {
                "store_id": str(store.id),
                "type": ProductType.DIY_KIT,
                "category_id": str(cat.id),
                "name": "X",
                "slug": "x",
                "base_price_cents": 100,
                "attributes": {"foo": "bar"},
            },
            format="json",
        )
        assert r.status_code == 400


@pytest.mark.django_db
class TestProductListIsolation:
    def test_seller_sees_only_own(self):
        a = _seller("a@x.com")
        b = _seller("b@x.com")
        s_a = _store(a, name="A", slug="a")
        s_b = _store(b, name="B", slug="b")
        cat = _category()
        Product.objects.create(
            store=s_a,
            type=ProductType.DIY_KIT,
            category=cat,
            name="Pa",
            slug="pa",
            base_price_cents=100,
        )
        Product.objects.create(
            store=s_b,
            type=ProductType.DIY_KIT,
            category=cat,
            name="Pb",
            slug="pb",
            base_price_cents=100,
        )

        c = APIClient()
        c.force_authenticate(user=a)
        r = c.get(reverse("catalog:product-list"))
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["name"] == "Pa"

    def test_super_admin_sees_all(self):
        admin = User.objects.create_user(email="admin@x.com", password="long-password-123")
        admin.role = RoleChoices.SUPER_ADMIN
        admin.save()
        a = _seller("a@x.com")
        s = _store(a, name="A", slug="a")
        cat = _category()
        Product.objects.create(
            store=s,
            type=ProductType.DIY_KIT,
            category=cat,
            name="P",
            slug="p",
            base_price_cents=100,
        )

        c = APIClient()
        c.force_authenticate(user=admin)
        r = c.get(reverse("catalog:product-list"))
        assert r.status_code == 200
        assert len(r.json()) == 1


@pytest.mark.django_db
class TestProductDetailIsolation:
    def test_other_seller_gets_404(self):
        a = _seller("a@x.com")
        b = _seller("b@x.com")
        s_b = _store(b, name="B", slug="b")
        cat = _category()
        p_b = Product.objects.create(
            store=s_b,
            type=ProductType.DIY_KIT,
            category=cat,
            name="Pb",
            slug="pb",
            base_price_cents=100,
        )

        c = APIClient()
        c.force_authenticate(user=a)
        r = c.get(reverse("catalog:product-detail", args=[p_b.id]))
        assert r.status_code == 404

    def test_patch_other_seller_404(self):
        a = _seller("a@x.com")
        b = _seller("b@x.com")
        s_b = _store(b, name="B", slug="b")
        cat = _category()
        p_b = Product.objects.create(
            store=s_b,
            type=ProductType.DIY_KIT,
            category=cat,
            name="Pb",
            slug="pb",
            base_price_cents=100,
        )

        c = APIClient()
        c.force_authenticate(user=a)
        r = c.patch(
            reverse("catalog:product-detail", args=[p_b.id]),
            {"name": "Hacked"},
            format="json",
        )
        assert r.status_code == 404
        p_b.refresh_from_db()
        assert p_b.name == "Pb"

    def test_delete_other_seller_404(self):
        a = _seller("a@x.com")
        b = _seller("b@x.com")
        s_b = _store(b, name="B", slug="b")
        cat = _category()
        p_b = Product.objects.create(
            store=s_b,
            type=ProductType.DIY_KIT,
            category=cat,
            name="Pb",
            slug="pb",
            base_price_cents=100,
        )

        c = APIClient()
        c.force_authenticate(user=a)
        r = c.delete(reverse("catalog:product-detail", args=[p_b.id]))
        assert r.status_code == 404
        assert Product.objects.filter(id=p_b.id).exists()
