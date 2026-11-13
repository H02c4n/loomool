import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import (
    Category,
    Product,
    ProductType,
    ProductVariant,
)
from apps.stores.models import Store

User = get_user_model()


@pytest.fixture
def seller_with_kit(db):
    seller = User.objects.create_user(
        email="flow@example.com", password="long-password-123"
    )
    store = Store.objects.create(name="Flow", slug="flow", owner=seller)
    cat = Category.objects.create(name="K", slug="k")
    kit = Product.objects.create(
        store=store,
        type=ProductType.DIY_KIT,
        category=cat,
        name="Kit",
        slug="kit",
        base_price_cents=100,
    )
    yarn = Product.objects.create(
        store=store,
        type=ProductType.MATERIAL,
        category=cat,
        name="Yarn",
        slug="yarn",
        base_price_cents=50,
    )
    return {
        "seller": seller,
        "kit_variant": ProductVariant.objects.create(product=kit, sku="K-1"),
        "yarn_variant": ProductVariant.objects.create(product=yarn, sku="Y-1"),
    }


@pytest.mark.django_db
class TestSessionCsrfFlow:
    """
    Real session cookie + real CSRF token + state-changing endpoint.
    Uses force_login (not force_authenticate) so the session cookie is
    real, and prime_headers=False so we control CSRF manually.
    """

    def test_bom_post_with_session_and_csrf_succeeds(self, seller_with_kit):
        c = APIClient(enforce_csrf_checks=True)
        c.force_login(seller_with_kit["seller"])
        # Prime CSRF cookie
        c.get(reverse("auth:csrf"))
        token = c.cookies["csrftoken"].value

        r = c.post(
            reverse("catalog:bom-list-add", args=[seller_with_kit["kit_variant"].id]),
            {
                "component_variant_id": str(seller_with_kit["yarn_variant"].id),
                "quantity": 2,
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert r.status_code == 201, r.content

    def test_bom_post_with_session_but_no_csrf_rejected(self, seller_with_kit):
        c = APIClient(enforce_csrf_checks=True)
        c.force_login(seller_with_kit["seller"])

        r = c.post(
            reverse("catalog:bom-list-add", args=[seller_with_kit["kit_variant"].id]),
            {
                "component_variant_id": str(seller_with_kit["yarn_variant"].id),
                "quantity": 2,
            },
            format="json",
        )
        assert r.status_code == 403