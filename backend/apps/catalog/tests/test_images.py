from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductImage, ProductType
from apps.stores.models import Store

User = get_user_model()


def _setup():
    seller = User.objects.create_user(email="seller@example.com", password="long-password-123")
    store = Store.objects.create(name="Loom", slug="loom", owner=seller)
    cat = Category.objects.create(name="K", slug="k")
    product = Product.objects.create(
        store=store,
        type=ProductType.DIY_KIT,
        category=cat,
        name="P",
        slug="p",
        base_price_cents=100,
    )
    return seller, product


def _png_bytes(w=400, h=300, color=(255, 0, 0)):
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w=400, h=300, color=(0, 255, 0)):
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.django_db
class TestImageUpload:
    def test_upload_png(self):
        seller, product = _setup()
        c = APIClient()
        c.force_authenticate(user=seller)
        uploaded = SimpleUploadedFile("a.png", _png_bytes(), content_type="image/png")
        r = c.post(
            reverse("catalog:product-image-upload", args=[product.id]),
            {"file": uploaded, "alt_text": "A knitted bag"},
            format="multipart",
        )
        assert r.status_code == 201, r.content
        assert ProductImage.objects.count() == 1
        image = ProductImage.objects.first()
        assert image.width == 400
        assert image.height == 300
        assert image.storage_key_original.endswith("_original.webp")
        assert image.storage_key_thumb.endswith("_thumb.webp")

    def test_upload_jpeg(self):
        seller, product = _setup()
        c = APIClient()
        c.force_authenticate(user=seller)
        uploaded = SimpleUploadedFile("a.jpg", _jpeg_bytes(), content_type="image/jpeg")
        r = c.post(
            reverse("catalog:product-image-upload", args=[product.id]),
            {"file": uploaded},
            format="multipart",
        )
        assert r.status_code == 201

    def test_reject_svg(self):
        seller, product = _setup()
        c = APIClient()
        c.force_authenticate(user=seller)
        uploaded = SimpleUploadedFile(
            "evil.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            content_type="image/svg+xml",
        )
        r = c.post(
            reverse("catalog:product-image-upload", args=[product.id]),
            {"file": uploaded},
            format="multipart",
        )
        assert r.status_code == 400
        assert ProductImage.objects.count() == 0

    def test_reject_html(self):
        seller, product = _setup()
        c = APIClient()
        c.force_authenticate(user=seller)
        uploaded = SimpleUploadedFile(
            "evil.html",
            b"<!DOCTYPE html><html><body>x</body></html>",
            content_type="text/html",
        )
        r = c.post(
            reverse("catalog:product-image-upload", args=[product.id]),
            {"file": uploaded},
            format="multipart",
        )
        assert r.status_code == 400

    def test_reject_non_image(self):
        seller, product = _setup()
        c = APIClient()
        c.force_authenticate(user=seller)
        uploaded = SimpleUploadedFile("x.txt", b"hello world", content_type="text/plain")
        r = c.post(
            reverse("catalog:product-image-upload", args=[product.id]),
            {"file": uploaded},
            format="multipart",
        )
        assert r.status_code == 400

    def test_other_seller_cannot_upload(self):
        _, product = _setup()
        other = User.objects.create_user(email="other@example.com", password="long-password-123")
        c = APIClient()
        c.force_authenticate(user=other)
        uploaded = SimpleUploadedFile("a.png", _png_bytes(), content_type="image/png")
        r = c.post(
            reverse("catalog:product-image-upload", args=[product.id]),
            {"file": uploaded},
            format="multipart",
        )
        assert r.status_code == 404
        assert ProductImage.objects.count() == 0
