import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0001_cart_favorite"),
        ("catalog", "0004_search_indexes"),
        ("stores", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING_PAYMENT", "Pending payment"),
                            ("PAID", "Paid"),
                            ("PROCESSING", "Processing"),
                            ("PARTIALLY_SHIPPED", "Partially shipped"),
                            ("SHIPPED", "Shipped"),
                            ("DELIVERED", "Delivered"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                            ("PARTIALLY_REFUNDED", "Partially refunded"),
                            ("REFUNDED", "Refunded"),
                            ("DISPUTED", "Disputed"),
                        ],
                        db_index=True,
                        default="PENDING_PAYMENT",
                        max_length=24,
                    ),
                ),
                ("total_cents", models.BigIntegerField(default=0)),
                ("currency", models.CharField(default="SEK", max_length=3)),
                ("shipping_address", models.JSONField(blank=True, default=dict)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SellerOrder",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING_PAYMENT", "Pending payment"),
                            ("PAID", "Paid"),
                            ("PROCESSING", "Processing"),
                            ("PARTIALLY_SHIPPED", "Partially shipped"),
                            ("SHIPPED", "Shipped"),
                            ("DELIVERED", "Delivered"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                            ("PARTIALLY_REFUNDED", "Partially refunded"),
                            ("REFUNDED", "Refunded"),
                            ("DISPUTED", "Disputed"),
                        ],
                        default="PENDING_PAYMENT",
                        max_length=24,
                    ),
                ),
                ("subtotal_cents", models.BigIntegerField(default=0)),
                ("currency", models.CharField(default="SEK", max_length=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seller_orders",
                        to="shop.order",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="seller_orders",
                        to="stores.store",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
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
                ("product_name", models.CharField(max_length=200)),
                ("variant_sku", models.CharField(max_length=64)),
                ("variant_options", models.JSONField(blank=True, default=dict)),
                ("unit_price_cents", models.BigIntegerField()),
                ("quantity", models.PositiveSmallIntegerField()),
                ("line_total_cents", models.BigIntegerField()),
                ("tax_class", models.CharField(default="STANDARD", max_length=32)),
                ("tax_rate_percent", models.IntegerField(default=25)),
                ("commission_rate_percent", models.IntegerField()),
                (
                    "commission_rule_version",
                    models.CharField(default="phase5-default", max_length=32),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "seller_order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="shop.sellerorder",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="order_items",
                        to="catalog.productvariant",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="OrderStatusHistory",
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
                    "from_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("PENDING_PAYMENT", "Pending payment"),
                            ("PAID", "Paid"),
                            ("PROCESSING", "Processing"),
                            ("PARTIALLY_SHIPPED", "Partially shipped"),
                            ("SHIPPED", "Shipped"),
                            ("DELIVERED", "Delivered"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                            ("PARTIALLY_REFUNDED", "Partially refunded"),
                            ("REFUNDED", "Refunded"),
                            ("DISPUTED", "Disputed"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("PENDING_PAYMENT", "Pending payment"),
                            ("PAID", "Paid"),
                            ("PROCESSING", "Processing"),
                            ("PARTIALLY_SHIPPED", "Partially shipped"),
                            ("SHIPPED", "Shipped"),
                            ("DELIVERED", "Delivered"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                            ("PARTIALLY_REFUNDED", "Partially refunded"),
                            ("REFUNDED", "Refunded"),
                            ("DISPUTED", "Disputed"),
                        ],
                        max_length=24,
                    ),
                ),
                ("reason", models.CharField(blank=True, max_length=200)),
                ("actor_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="shop.order",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="SellerOrderStatusHistory",
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
                    "from_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("PENDING_PAYMENT", "Pending payment"),
                            ("PAID", "Paid"),
                            ("PROCESSING", "Processing"),
                            ("PARTIALLY_SHIPPED", "Partially shipped"),
                            ("SHIPPED", "Shipped"),
                            ("DELIVERED", "Delivered"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                            ("PARTIALLY_REFUNDED", "Partially refunded"),
                            ("REFUNDED", "Refunded"),
                            ("DISPUTED", "Disputed"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("PENDING_PAYMENT", "Pending payment"),
                            ("PAID", "Paid"),
                            ("PROCESSING", "Processing"),
                            ("PARTIALLY_SHIPPED", "Partially shipped"),
                            ("SHIPPED", "Shipped"),
                            ("DELIVERED", "Delivered"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                            ("PARTIALLY_REFUNDED", "Partially refunded"),
                            ("REFUNDED", "Refunded"),
                            ("DISPUTED", "Disputed"),
                        ],
                        max_length=24,
                    ),
                ),
                ("reason", models.CharField(blank=True, max_length=200)),
                ("actor_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "seller_order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="shop.sellerorder",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.CheckConstraint(
                condition=models.Q(("total_cents__gte", 0)),
                name="order_total_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="sellerorder",
            constraint=models.UniqueConstraint(
                fields=("order", "store"), name="seller_order_unique_per_store"
            ),
        ),
        migrations.AddConstraint(
            model_name="sellerorder",
            constraint=models.CheckConstraint(
                condition=models.Q(("subtotal_cents__gte", 0)),
                name="seller_order_subtotal_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gte", 1)),
                name="order_item_quantity_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("unit_price_cents__gte", 0)),
                name="order_item_unit_price_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("line_total_cents__gte", 0)),
                name="order_item_line_total_non_negative",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["user", "-created_at"],
                name="shop_order_user_id_f8b1c9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["status", "expires_at"],
                name="shop_order_status_ffc48e_idx",
            ),
        ),
    ]
