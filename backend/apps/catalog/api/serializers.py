from rest_framework import serializers

from apps.catalog.models import (
    Category,
    CategoryAttributeDefinition,
    Product,
    ProductComponent,
    ProductImage,
    ProductOptionDefinition,
    ProductRelationship,
    ProductType,
    ProductVariant,
    RelationshipType,
)


class CategoryAttributeDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryAttributeDefinition
        fields = (
            "id",
            "key",
            "label",
            "type",
            "required",
            "options",
            "sort_order",
        )
        read_only_fields = fields


class CategoryListSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "sort_order", "children")
        read_only_fields = fields

    def get_children(self, category):
        children = category.children.filter(is_active=True).order_by("sort_order", "name")
        return CategoryListSerializer(children, many=True, context=self.context).data


class CategoryFlatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "sort_order")
        read_only_fields = fields


class CategoryDetailSerializer(serializers.ModelSerializer):
    attribute_definitions = CategoryAttributeDefinitionSerializer(many=True)
    parent = CategoryFlatSerializer(read_only=True)

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "is_active",
            "sort_order",
            "parent",
            "attribute_definitions",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProductOptionDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOptionDefinition
        fields = ("id", "key", "label", "values", "sort_order")
        read_only_fields = ("id",)


class ProductVariantSerializer(serializers.ModelSerializer):
    effective_price_cents = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "price_cents",
            "options",
            "weight_g",
            "is_active",
            "effective_price_cents",
        )
        read_only_fields = ("id", "effective_price_cents")


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = (
            "id",
            "storage_key_original",
            "storage_key_medium",
            "storage_key_thumb",
            "width",
            "height",
            "byte_size",
            "alt_text",
            "sort_order",
        )
        read_only_fields = fields


class ProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id",
            "store",
            "type",
            "category",
            "name",
            "slug",
            "base_price_cents",
            "currency",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class ProductDetailSerializer(serializers.ModelSerializer):
    option_definitions = ProductOptionDefinitionSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "store",
            "type",
            "category",
            "name",
            "slug",
            "description",
            "base_price_cents",
            "currency",
            "tax_class",
            "weight_g",
            "dimensions",
            "attributes",
            "is_active",
            "published_at",
            "created_at",
            "updated_at",
            "option_definitions",
            "variants",
            "images",
        )
        read_only_fields = fields


class ProductCreateSerializer(serializers.Serializer):
    store_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=ProductType.choices)
    category_id = serializers.UUIDField()
    name = serializers.CharField(max_length=200)
    slug = serializers.SlugField(max_length=220)
    description = serializers.CharField(allow_blank=True, default="")
    base_price_cents = serializers.IntegerField(min_value=0)
    currency = serializers.CharField(max_length=3, default="SEK")
    tax_class = serializers.CharField(max_length=32, default="STANDARD")
    weight_g = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    dimensions = serializers.JSONField(required=False, default=dict)
    attributes = serializers.JSONField(required=False, default=dict)
    is_active = serializers.BooleanField(default=True)
    published_at = serializers.DateTimeField(required=False, allow_null=True)


class ProductUpdateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ProductType.choices, required=False)
    category_id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=200, required=False)
    slug = serializers.SlugField(max_length=220, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    base_price_cents = serializers.IntegerField(min_value=0, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    tax_class = serializers.CharField(max_length=32, required=False)
    weight_g = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    dimensions = serializers.JSONField(required=False)
    attributes = serializers.JSONField(required=False)
    is_active = serializers.BooleanField(required=False)
    published_at = serializers.DateTimeField(required=False, allow_null=True)


class ProductComponentSerializer(serializers.ModelSerializer):
    component_variant_sku = serializers.CharField(source="component_variant.sku", read_only=True)
    component_product_name = serializers.CharField(
        source="component_variant.product.name", read_only=True
    )

    class Meta:
        model = ProductComponent
        fields = (
            "id",
            "kit_variant",
            "component_variant",
            "component_variant_sku",
            "component_product_name",
            "quantity",
            "sort_order",
        )
        read_only_fields = ("id", "component_variant_sku", "component_product_name")


class BOMAddSerializer(serializers.Serializer):
    component_variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    sort_order = serializers.IntegerField(min_value=0, default=0)


class ProductRelationshipSerializer(serializers.ModelSerializer):
    to_product_name = serializers.CharField(source="to_product.name", read_only=True)
    to_product_slug = serializers.CharField(source="to_product.slug", read_only=True)

    class Meta:
        model = ProductRelationship
        fields = (
            "id",
            "from_product",
            "to_product",
            "to_product_name",
            "to_product_slug",
            "relationship_type",
            "created_at",
        )
        read_only_fields = (
            "id",
            "from_product",
            "created_at",
            "to_product_name",
            "to_product_slug",
        )


class RelationshipAddSerializer(serializers.Serializer):
    to_product_id = serializers.UUIDField()
    relationship_type = serializers.ChoiceField(choices=RelationshipType.choices)
