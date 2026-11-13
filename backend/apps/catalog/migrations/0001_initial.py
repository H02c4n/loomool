import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=140)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="catalog.category",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="CategoryAttributeDefinition",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                message=(
                                    "Attribute key must be lowercase, start with a "
                                    "letter, and contain only a-z, 0-9, _."
                                ),
                                regex="^[a-z][a-z0-9_]*$",
                            )
                        ],
                    ),
                ),
                ("label", models.CharField(max_length=120)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("TEXT", "Text"),
                            ("INTEGER", "Integer"),
                            ("DECIMAL", "Decimal"),
                            ("BOOLEAN", "Boolean"),
                            ("ENUM", "Enum"),
                        ],
                        max_length=20,
                    ),
                ),
                ("required", models.BooleanField(default=False)),
                ("options", models.JSONField(blank=True, default=list)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attribute_definitions",
                        to="catalog.category",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "key"],
            },
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                fields=("parent", "slug"), name="category_parent_slug_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                condition=models.Q(("parent__isnull", True)),
                fields=("slug",),
                name="category_root_slug_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="categoryattributedefinition",
            constraint=models.UniqueConstraint(
                fields=("category", "key"), name="category_attr_key_unique"
            ),
        ),
    ]