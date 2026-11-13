import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import (
    AttributeType,
    Category,
    CategoryAttributeDefinition,
)


@pytest.mark.django_db
class TestCategoryModel:
    def test_create_root(self):
        c = Category.objects.create(name="Örgü", slug="orgu")
        assert c.parent is None
        assert c.is_active is True

    def test_create_child(self):
        parent = Category.objects.create(name="Örgü", slug="orgu")
        child = Category.objects.create(name="Kitler", slug="kitler", parent=parent)
        assert child.parent == parent

    def test_slug_unique_same_parent(self):
        parent = Category.objects.create(name="P", slug="p")
        Category.objects.create(name="A", slug="dup", parent=parent)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="B", slug="dup", parent=parent)

    def test_same_slug_different_parent_ok(self):
        a = Category.objects.create(name="A", slug="a")
        b = Category.objects.create(name="B", slug="b")
        Category.objects.create(name="X", slug="dup", parent=a)
        Category.objects.create(name="Y", slug="dup", parent=b)
        assert Category.objects.filter(slug="dup").count() == 2

    def test_root_slug_unique(self):
        Category.objects.create(name="A", slug="dup")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="B", slug="dup")

    def test_self_parent_rejected(self):
        c = Category.objects.create(name="A", slug="a")
        c.parent = c
        with pytest.raises(ValidationError):
            c.save()

    def test_cycle_rejected(self):
        a = Category.objects.create(name="A", slug="a")
        b = Category.objects.create(name="B", slug="b", parent=a)
        a.parent = b
        with pytest.raises(ValidationError):
            a.save()


@pytest.mark.django_db
class TestAttributeDefinitionModel:
    def test_unique_key_per_category(self):
        c = Category.objects.create(name="A", slug="a")
        CategoryAttributeDefinition.objects.create(
            category=c, key="yarn_type", label="Yarn type", type=AttributeType.TEXT
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CategoryAttributeDefinition.objects.create(
                    category=c,
                    key="yarn_type",
                    label="Yarn type",
                    type=AttributeType.TEXT,
                )

    def test_enum_requires_options(self):
        c = Category.objects.create(name="A", slug="a")
        attr = CategoryAttributeDefinition(
            category=c, key="color", label="Color", type=AttributeType.ENUM
        )
        with pytest.raises(ValidationError):
            attr.save()

    def test_non_enum_rejects_options(self):
        c = Category.objects.create(name="A", slug="a")
        attr = CategoryAttributeDefinition(
            category=c,
            key="size",
            label="Size",
            type=AttributeType.TEXT,
            options=["S", "M"],
        )
        with pytest.raises(ValidationError):
            attr.save()


@pytest.mark.django_db
class TestCategoryAPI:
    def test_list_returns_tree(self):
        parent = Category.objects.create(name="Örgü", slug="orgu")
        Category.objects.create(name="Kitler", slug="kitler", parent=parent)

        r = APIClient().get(reverse("catalog:category-list"))
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["slug"] == "orgu"
        assert len(data[0]["children"]) == 1
        assert data[0]["children"][0]["slug"] == "kitler"

    def test_list_flat(self):
        parent = Category.objects.create(name="A", slug="a")
        Category.objects.create(name="B", slug="b", parent=parent)

        r = APIClient().get(reverse("catalog:category-list") + "?flat=true")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert {row["slug"] for row in data} == {"a", "b"}

    def test_list_excludes_inactive(self):
        Category.objects.create(name="A", slug="a", is_active=True)
        Category.objects.create(name="B", slug="b", is_active=False)

        r = APIClient().get(reverse("catalog:category-list"))
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["slug"] == "a"

    def test_detail_includes_attributes(self):
        c = Category.objects.create(name="A", slug="a")
        CategoryAttributeDefinition.objects.create(
            category=c,
            key="yarn_type",
            label="Yarn type",
            type=AttributeType.TEXT,
            required=True,
        )

        r = APIClient().get(reverse("catalog:category-detail", args=["a"]))
        assert r.status_code == 200
        data = r.json()
        assert data["slug"] == "a"
        assert len(data["attribute_definitions"]) == 1
        assert data["attribute_definitions"][0]["key"] == "yarn_type"
        assert data["attribute_definitions"][0]["required"] is True

    def test_detail_inactive_returns_404(self):
        Category.objects.create(name="A", slug="a", is_active=False)
        r = APIClient().get(reverse("catalog:category-detail", args=["a"]))
        assert r.status_code == 404

    def test_detail_unknown_slug_returns_404(self):
        r = APIClient().get(reverse("catalog:category-detail", args=["nope"]))
        assert r.status_code == 404
