import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Product",
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
                    "type",
                    models.CharField(
                        choices=[
                            ("DIY_KIT", "DIY kit"),
                            ("MATERIAL", "Material"),
                            ("FINISHED_HANDMADE", "Finished handmade"),
                            ("DIGITAL_PATTERN", "Digital pattern"),
                            ("WORKSHOP", "Workshop"),
                            ("BUNDLE", "Bundle"),
                        ],
                        max_length=32,
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("base_price_cents", models.BigIntegerField()),
                ("currency", models.CharField(default="SEK", max_length=3)),
                ("tax_class", models.CharField(default="STANDARD", max_length=32)),
                ("weight_g", models.IntegerField(blank=True, null=True)),
                ("dimensions", models.JSONField(blank=True, default=dict)),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="products",
                        to="catalog.category",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="products",
                        to="stores.store",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ProductOptionDefinition",
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
                ("values", models.JSONField(default=list)),
                ("sort_order", models.IntegerField(default=0)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="option_definitions",
                        to="catalog.product",
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "key"]},
        ),
        migrations.CreateModel(
            name="ProductVariant",
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
                ("sku", models.CharField(max_length=64)),
                ("price_cents", models.BigIntegerField(blank=True, null=True)),
                ("options", models.JSONField(blank=True, default=dict)),
                ("weight_g", models.IntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="catalog.product",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="ProductImage",
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
                ("storage_key_original", models.CharField(max_length=500)),
                ("storage_key_medium", models.CharField(max_length=500)),
                ("storage_key_thumb", models.CharField(max_length=500)),
                ("width", models.IntegerField()),
                ("height", models.IntegerField()),
                ("byte_size", models.BigIntegerField()),
                ("alt_text", models.CharField(blank=True, max_length=200)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="catalog.product",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="catalog.productvariant",
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("store", "slug"), name="product_store_slug_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(("base_price_cents__gte", 0)),
                name="product_base_price_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="productoptiondefinition",
            constraint=models.UniqueConstraint(
                fields=("product", "key"), name="product_option_key_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(
                fields=("product", "sku"), name="variant_product_sku_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("price_cents__isnull", True))
                    | models.Q(("price_cents__gte", 0))
                ),
                name="variant_price_non_negative",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["category", "is_active"], name="catalog_pro_category_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["store", "is_active"], name="catalog_pro_store_idx"
            ),
        ),
    ]
