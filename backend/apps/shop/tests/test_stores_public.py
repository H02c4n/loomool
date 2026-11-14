import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.stores.models import Store


@pytest.mark.django_db
class TestStorePublic:
    def test_anonymous_can_view_store_and_products(
        self, store, category_child, product_factory, seller
    ):
        store.owner.first_name = "Anna"
        store.owner.last_name = "Maker"
        store.owner.save()
        product_factory(store=store, category=category_child, name="P1", slug="p1")
        product_factory(store=store, category=category_child, name="P2", slug="p2")

        r = APIClient().get(reverse("shop:store-detail", args=[store.slug]))
        assert r.status_code == 200
        body = r.json()
        assert body["store"]["slug"] == "loom"
        assert body["store"]["owner_display_name"] == "Anna Maker"
        assert body["store"]["product_count"] == 2
        assert len(body["products"]) == 2

    def test_inactive_store_returns_404(self, store):
        Store.objects.filter(id=store.id).update(is_active=False)
        r = APIClient().get(reverse("shop:store-detail", args=[store.slug]))
        assert r.status_code == 404

    def test_store_only_shows_active_products(self, store, category_child, product_factory):
        product_factory(store=store, category=category_child, name="On", slug="on")
        product_factory(
            store=store,
            category=category_child,
            name="Off",
            slug="off",
            is_active=False,
        )
        r = APIClient().get(reverse("shop:store-detail", args=[store.slug]))
        assert r.status_code == 200
        assert len(r.json()["products"]) == 1
        assert r.json()["products"][0]["slug"] == "on"
