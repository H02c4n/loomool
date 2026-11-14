import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestProductSearch:
    def test_search_finds_by_name(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="Knitted bag kit",
            slug="knitted-bag",
        )
        product_factory(
            store=store,
            category=category_child,
            name="Cotton yarn",
            slug="cotton-yarn",
        )
        r = APIClient().get(reverse("shop:product-list"), {"q": "knitted"})
        assert r.status_code == 200
        assert r.json()["count"] >= 1
        slugs = [p["slug"] for p in r.json()["results"]]
        assert "knitted-bag" in slugs

    def test_search_finds_by_description(self, store, category_child, product_factory):
        from apps.catalog.models import Product

        product_factory(
            store=store,
            category=category_child,
            name="X",
            slug="x",
        )
        p = Product.objects.get(slug="x")
        p.description = "A very warm wooly sweater kit for winter"
        p.save()
        r = APIClient().get(reverse("shop:product-list"), {"q": "sweater"})
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_search_empty_returns_all(self, store, category_child, product_factory):
        product_factory(store=store, category=category_child, name="A", slug="a")
        product_factory(store=store, category=category_child, name="B", slug="b")
        r = APIClient().get(reverse("shop:product-list"))
        assert r.json()["count"] == 2

    def test_search_no_match_returns_empty(self, store, category_child, product_factory):
        product_factory(store=store, category=category_child, name="A", slug="a")
        r = APIClient().get(reverse("shop:product-list"), {"q": "zzzznonexistent"})
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_trigram_fallback_for_typo(self, store, category_child, product_factory):
        # "knittd" is a typo of "knitted"; trigram should still match.
        product_factory(
            store=store,
            category=category_child,
            name="Knitted bag",
            slug="knitted-bag",
        )
        # Another product with a different name, so FTS has no match for "knittd".
        product_factory(
            store=store,
            category=category_child,
            name="Cotton yarn",
            slug="cotton-yarn",
        )
        r = APIClient().get(reverse("shop:product-list"), {"q": "knittd"})
        assert r.status_code == 200
        # At least one result should appear via trigram.
        assert r.json()["count"] >= 1
