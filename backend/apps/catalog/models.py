import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from .managers import CategoryManager, ProductScopedManager

ATTRIBUTE_KEY_VALIDATOR = RegexValidator(
    regex=r"^[a-z][a-z0-9_]*$",
    message="Attribute key must be lowercase, start with a letter, and contain only a-z, 0-9, _.",
)


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CategoryManager()

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "slug"], name="category_parent_slug_unique"),
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(parent__isnull=True),
                name="category_root_slug_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.parent_id:
            if self.parent_id == self.id:
                raise ValidationError({"parent": "Category cannot be its own parent."})
            seen: set = set()
            node: Category | None = self.parent
            while node is not None:
                if node.id == self.id:
                    raise ValidationError({"parent": "Category cycle detected."})
                if node.id in seen:
                    raise ValidationError({"parent": "Existing cycle detected in parent chain."})
                seen.add(node.id)
                node = node.parent


class AttributeType(models.TextChoices):
    TEXT = "TEXT", "Text"
    INTEGER = "INTEGER", "Integer"
    DECIMAL = "DECIMAL", "Decimal"
    BOOLEAN = "BOOLEAN", "Boolean"
    ENUM = "ENUM", "Enum"


class CategoryAttributeDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="attribute_definitions"
    )
    key = models.CharField(max_length=64, validators=[ATTRIBUTE_KEY_VALIDATOR])
    label = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=AttributeType.choices)
    required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "key"]
        constraints = [
            models.UniqueConstraint(fields=["category", "key"], name="category_attr_key_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.category_id}:{self.key}"

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.type == AttributeType.ENUM and not self.options:
            raise ValidationError({"options": "ENUM attribute requires a non-empty options list."})
        if self.type != AttributeType.ENUM and self.options:
            raise ValidationError({"options": "options is only allowed for ENUM attributes."})


# ---- Enums ---------------------------------------------------------------


class ProductType(models.TextChoices):
    DIY_KIT = "DIY_KIT", "DIY kit"
    MATERIAL = "MATERIAL", "Material"
    FINISHED_HANDMADE = "FINISHED_HANDMADE", "Finished handmade"
    DIGITAL_PATTERN = "DIGITAL_PATTERN", "Digital pattern"
    WORKSHOP = "WORKSHOP", "Workshop"
    BUNDLE = "BUNDLE", "Bundle"


# ---- Product -------------------------------------------------------------


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="products",
    )
    type = models.CharField(max_length=32, choices=ProductType.choices)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)

    base_price_cents = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="SEK")
    tax_class = models.CharField(max_length=32, default="STANDARD")

    weight_g = models.IntegerField(null=True, blank=True)
    dimensions = models.JSONField(default=dict, blank=True)
    attributes = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductScopedManager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="product_store_slug_unique"),
            models.CheckConstraint(
                condition=Q(base_price_cents__gte=0),
                name="product_base_price_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["store", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name


# ---- Option definitions --------------------------------------------------


class ProductOptionDefinition(models.Model):
    """Defines which options this product offers (e.g. color, size)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="option_definitions"
    )
    key = models.CharField(max_length=64, validators=[ATTRIBUTE_KEY_VALIDATOR])
    label = models.CharField(max_length=120)
    values = models.JSONField(default=list)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "key"]
        constraints = [
            models.UniqueConstraint(fields=["product", "key"], name="product_option_key_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.key}"


# ---- Variants ------------------------------------------------------------


class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64)
    price_cents = models.BigIntegerField(null=True, blank=True)
    options = models.JSONField(default=dict, blank=True)
    weight_g = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "sku"], name="variant_product_sku_unique"),
            models.CheckConstraint(
                condition=Q(price_cents__isnull=True) | Q(price_cents__gte=0),
                name="variant_price_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.sku}"

    @property
    def effective_price_cents(self) -> int:
        return self.price_cents if self.price_cents is not None else self.product.base_price_cents


# ---- Images --------------------------------------------------------------


class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="images",
    )
    storage_key_original = models.CharField(max_length=500)
    storage_key_medium = models.CharField(max_length=500)
    storage_key_thumb = models.CharField(max_length=500)
    width = models.IntegerField()
    height = models.IntegerField()
    byte_size = models.BigIntegerField()
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.id}"


# ---- Product relationships -----------------------------------------------


class RelationshipType(models.TextChoices):
    RELATED = "RELATED", "Related"
    COMPLEMENTARY = "COMPLEMENTARY", "Complementary"
    PATTERN_FOR = "PATTERN_FOR", "Pattern for"
    KIT_FOR = "KIT_FOR", "Kit for"
    WORKSHOP_FOR = "WORKSHOP_FOR", "Workshop for"


class ProductRelationship(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="outgoing_relationships"
    )
    to_product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="incoming_relationships"
    )
    relationship_type = models.CharField(max_length=24, choices=RelationshipType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_product", "to_product", "relationship_type"],
                name="relationship_unique",
            ),
            models.CheckConstraint(
                condition=~Q(from_product=models.F("to_product")),
                name="relationship_self_reference",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.from_product_id} " f"-[{self.relationship_type}]-> " f"{self.to_product_id}"


# ---- BOM (kit components) ------------------------------------------------


class ProductComponent(models.Model):
    """
    Bill of materials. `kit_variant` is a DIY_KIT variant; `component_variant`
    is the variant of the product that goes inside the kit.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kit_variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="components"
    )
    component_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="in_kits"
    )
    quantity = models.IntegerField(default=1)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["kit_variant", "component_variant"],
                name="component_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="component_quantity_positive"
            ),
            models.CheckConstraint(
                condition=~Q(kit_variant=models.F("component_variant")),
                name="component_self_reference",
            ),
        ]

    def __str__(self) -> str:
        return f"kit {self.kit_variant_id} " f"x{self.quantity} " f"{self.component_variant_id}"
