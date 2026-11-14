import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import ProductType


@pytest.mark.django_db
class TestProductListPublic:
    def test_anonymous_can_list_active_products(self, store, category_child, product_factory):
        p = product_factory(store=store, category=category_child, name="Bag kit", slug="bag-kit")
        r = APIClient().get(reverse("shop:product-list"))
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["id"] == str(p.id)

    def test_inactive_products_hidden(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="X",
            slug="x",
            is_active=False,
        )
        r = APIClient().get(reverse("shop:product-list"))
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_filter_by_category_includes_children(
        self,
        store,
        category_root,
        category_child,
        category_sibling,
        product_factory,
    ):
        product_factory(store=store, category=category_child, name="A", slug="a")
        product_factory(store=store, category=category_sibling, name="B", slug="b")
        r = APIClient().get(reverse("shop:product-list"), {"category": category_root.slug})
        assert r.status_code == 200
        assert r.json()["count"] == 2

    def test_filter_by_type(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="Kit",
            slug="kit",
            type=ProductType.DIY_KIT,
        )
        product_factory(
            store=store,
            category=category_child,
            name="Material",
            slug="mat",
            type=ProductType.MATERIAL,
        )
        r = APIClient().get(reverse("shop:product-list"), {"type": "MATERIAL"})
        assert r.status_code == 200
        assert r.json()["count"] == 1
        assert r.json()["results"][0]["slug"] == "mat"

    def test_filter_by_price_range(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="Cheap",
            slug="cheap",
            price_cents=100,
        )
        product_factory(
            store=store,
            category=category_child,
            name="Mid",
            slug="mid",
            price_cents=500,
        )
        product_factory(
            store=store,
            category=category_child,
            name="Rich",
            slug="rich",
            price_cents=1000,
        )
        r = APIClient().get(
            reverse("shop:product-list"),
            {"min_price_cents": 200, "max_price_cents": 700},
        )
        assert r.status_code == 200
        slugs = [p["slug"] for p in r.json()["results"]]
        assert slugs == ["mid"]

    def test_filter_in_stock(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="In",
            slug="in",
            stock=5,
        )
        product_factory(
            store=store,
            category=category_child,
            name="Out",
            slug="out",
            stock=0,
        )
        r = APIClient().get(reverse("shop:product-list"), {"in_stock": "true"})
        assert r.status_code == 200
        assert r.json()["count"] == 1
        assert r.json()["results"][0]["slug"] == "in"

    def test_sort_price_asc(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="Z",
            slug="z",
            price_cents=999,
        )
        product_factory(
            store=store,
            category=category_child,
            name="A",
            slug="a",
            price_cents=100,
        )
        r = APIClient().get(reverse("shop:product-list"), {"sort": "price_asc"})
        slugs = [p["slug"] for p in r.json()["results"]]
        assert slugs == ["a", "z"]

    def test_thumb_url_present_when_image(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="HasImg",
            slug="has-img",
            with_image=True,
        )
        r = APIClient().get(reverse("shop:product-list"))
        assert r.json()["results"][0]["thumb_url"] is not None


@pytest.mark.django_db
class TestProductDetailPublic:
    def test_anonymous_can_view(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="Bag",
            slug="bag-kit",
            with_image=True,
        )
        r = APIClient().get(
            reverse(
                "shop:product-detail",
                args=[store.slug, "bag-kit"],
            )
        )
        assert r.status_code == 200
        body = r.json()
        assert body["slug"] == "bag-kit"
        assert len(body["variants"]) == 1
        assert body["variants"][0]["in_stock"] is True
        assert len(body["images"]) == 1
        assert body["images"][0]["url_thumb"]

    def test_inactive_product_returns_404(self, store, category_child, product_factory):
        product_factory(
            store=store,
            category=category_child,
            name="Off",
            slug="off",
            is_active=False,
        )
        r = APIClient().get(reverse("shop:product-detail", args=[store.slug, "off"]))
        assert r.status_code == 404

    def test_wrong_store_slug_returns_404(self, store, category_child, product_factory):
        product_factory(store=store, category=category_child, name="X", slug="x")
        r = APIClient().get(reverse("shop:product-detail", args=["nope", "x"]))
        assert r.status_code == 404
