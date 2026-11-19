from django.core.files.storage import default_storage
from rest_framework import serializers

from apps.catalog.models import Product, ProductImage, ProductVariant
from apps.shop.models import CartItem, Favorite, Order, OrderItem, SellerOrder
from apps.stores.models import Store


class PublicImageSerializer(serializers.ModelSerializer):
    url_thumb = serializers.SerializerMethodField()
    url_medium = serializers.SerializerMethodField()
    url_original = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = (
            "id",
            "url_thumb",
            "url_medium",
            "url_original",
            "width",
            "height",
            "alt_text",
        )
        read_only_fields = fields

    def get_url_thumb(self, obj):
        return default_storage.url(obj.storage_key_thumb) if obj.storage_key_thumb else None

    def get_url_medium(self, obj):
        return default_storage.url(obj.storage_key_medium) if obj.storage_key_medium else None

    def get_url_original(self, obj):
        return default_storage.url(obj.storage_key_original) if obj.storage_key_original else None


class PublicVariantSerializer(serializers.ModelSerializer):
    effective_price_cents = serializers.IntegerField(read_only=True)
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ("id", "sku", "options", "effective_price_cents", "in_stock")
        read_only_fields = fields

    def get_in_stock(self, variant):
        inv = getattr(variant, "inventory", None)
        return bool(inv and inv.quantity_available > 0)


class PublicProductListSerializer(serializers.ModelSerializer):
    store_slug = serializers.CharField(source="store.slug", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    thumb_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "slug",
            "name",
            "type",
            "category_slug",
            "store_slug",
            "store_name",
            "base_price_cents",
            "currency",
            "thumb_url",
        )
        read_only_fields = fields

    def get_thumb_url(self, product):
        first_image = next(iter(product.images.all()), None)
        if first_image is None:
            return None
        return default_storage.url(first_image.storage_key_thumb)


class PublicProductDetailSerializer(PublicProductListSerializer):
    images = PublicImageSerializer(many=True, read_only=True)
    variants = PublicVariantSerializer(many=True, read_only=True)
    option_definitions = serializers.SerializerMethodField()

    class Meta(PublicProductListSerializer.Meta):
        fields = PublicProductListSerializer.Meta.fields + (
            "description",
            "attributes",
            "weight_g",
            "dimensions",
            "images",
            "variants",
            "option_definitions",
        )
        read_only_fields = fields

    def get_option_definitions(self, product):
        return [
            {
                "key": d.key,
                "label": d.label,
                "values": d.values,
            }
            for d in product.option_definitions.all()
        ]


class PublicStoreSerializer(serializers.ModelSerializer):
    owner_display_name = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ("id", "slug", "name", "owner_display_name", "product_count", "created_at")
        read_only_fields = fields

    def get_owner_display_name(self, store):
        owner = store.owner
        return owner.get_full_name() if hasattr(owner, "get_full_name") else ""

    def get_product_count(self, store):
        return store.products.filter(is_active=True).count()


# ---- Cart ------------------------------------------------------------------


class CartAddItemSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=10, default=1)


class CartUpdateItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=10)


class CartItemVariantSerializer(serializers.Serializer):
    """Compact variant info for a cart item."""

    id = serializers.UUIDField()
    sku = serializers.CharField()
    options = serializers.JSONField()
    effective_price_cents = serializers.IntegerField()


class CartItemProductSerializer(serializers.Serializer):
    """Compact product info for a cart item."""

    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    store_slug = serializers.CharField()
    store_name = serializers.CharField()
    thumb_url = serializers.CharField(allow_null=True)


class CartItemDetailSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    variant = serializers.SerializerMethodField()
    line_total_cents = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ("id", "product", "variant", "quantity", "line_total_cents")
        read_only_fields = fields

    def get_product(self, item):
        product = item.variant.product
        first_image = next(iter(product.images.all()), None)
        thumb = (
            default_storage.url(first_image.storage_key_thumb) if first_image is not None else None
        )
        return CartItemProductSerializer(
            {
                "id": product.id,
                "slug": product.slug,
                "name": product.name,
                "store_slug": product.store.slug,
                "store_name": product.store.name,
                "thumb_url": thumb,
            }
        ).data

    def get_variant(self, item):
        return CartItemVariantSerializer(
            {
                "id": item.variant.id,
                "sku": item.variant.sku,
                "options": item.variant.options,
                "effective_price_cents": item.variant.effective_price_cents,
            }
        ).data

    def get_line_total_cents(self, item):
        return item.variant.effective_price_cents * item.quantity


# ---- Favorites -------------------------------------------------------------


class FavoriteAddSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()


class FavoriteSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = ("id", "product", "created_at")
        read_only_fields = fields

    def get_product(self, favorite):
        product = favorite.product
        first_image = next(iter(product.images.all()), None)
        thumb = (
            default_storage.url(first_image.storage_key_thumb) if first_image is not None else None
        )
        return CartItemProductSerializer(
            {
                "id": product.id,
                "slug": product.slug,
                "name": product.name,
                "store_slug": product.store.slug,
                "store_name": product.store.name,
                "thumb_url": thumb,
            }
        ).data


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class OrderItemSerializer(serializers.ModelSerializer):
    product_slug = serializers.CharField(source="variant.product.slug", read_only=True)
    store_slug = serializers.CharField(source="variant.product.store.slug", read_only=True)
    store_name = serializers.CharField(source="variant.product.store.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "variant",
            "product_name",
            "variant_sku",
            "variant_options",
            "unit_price_cents",
            "quantity",
            "line_total_cents",
            "tax_class",
            "tax_rate_percent",
            "commission_rate_percent",
            "product_slug",
            "store_slug",
            "store_name",
        )
        read_only_fields = fields


class SellerOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    store_slug = serializers.CharField(source="store.slug", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)

    class Meta:
        model = SellerOrder
        fields = (
            "id",
            "store",
            "store_slug",
            "store_name",
            "status",
            "subtotal_cents",
            "currency",
            "items",
        )
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    seller_order_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "total_cents",
            "currency",
            "seller_order_count",
            "expires_at",
            "created_at",
        )
        read_only_fields = fields

    def get_seller_order_count(self, order):
        return order.seller_orders.count()


class OrderDetailSerializer(serializers.ModelSerializer):
    seller_orders = SellerOrderSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "total_cents",
            "currency",
            "shipping_address",
            "seller_orders",
            "expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=200)
