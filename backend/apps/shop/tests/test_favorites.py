import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType
from apps.shop.models import Favorite
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
        type=ProductType.DIY_KIT,
        name="P",
        slug="p",
        base_price_cents=100,
    )
    buyer = User.objects.create_user(email="b@x.com", password="long-password-123")
    return {"product": product, "buyer": buyer}


@pytest.mark.django_db
class TestFavorites:
    def test_anonymous_blocked(self, setup):
        c = APIClient()
        r = c.get(reverse("shop:favorite-list"))
        assert r.status_code in (401, 403)

    def test_toggle_on_and_off(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])

        r = c.post(
            reverse("shop:favorite-toggle"),
            {"product_id": str(setup["product"].id)},
            format="json",
        )
        assert r.status_code == 201
        assert Favorite.objects.count() == 1

        r = c.post(
            reverse("shop:favorite-toggle"),
            {"product_id": str(setup["product"].id)},
            format="json",
        )
        assert r.status_code == 204
        assert Favorite.objects.count() == 0

    def test_list_returns_user_favorites(self, setup):
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        c.post(
            reverse("shop:favorite-toggle"),
            {"product_id": str(setup["product"].id)},
            format="json",
        )
        r = c.get(reverse("shop:favorite-list"))
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["product"]["slug"] == "p"

    def test_two_users_isolated(self, setup):
        other = User.objects.create_user(email="o@x.com", password="long-password-123")
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        c.post(
            reverse("shop:favorite-toggle"),
            {"product_id": str(setup["product"].id)},
            format="json",
        )

        c2 = APIClient()
        c2.force_authenticate(user=other)
        r = c2.get(reverse("shop:favorite-list"))
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_inactive_product_not_favoritable(self, setup):
        setup["product"].is_active = False
        setup["product"].save()
        c = APIClient()
        c.force_authenticate(user=setup["buyer"])
        r = c.post(
            reverse("shop:favorite-toggle"),
            {"product_id": str(setup["product"].id)},
            format="json",
        )
        assert r.status_code == 404
