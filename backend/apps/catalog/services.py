from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import log_action
from apps.catalog.models import (
    AttributeType,
    Category,
    CategoryAttributeDefinition,
    Product,
    ProductType,
)

# Which product types allow BOM components.
BOM_ALLOWED_TYPES = {ProductType.DIY_KIT}


def validate_attributes(*, category: Category, attributes: dict) -> dict:
    """
    Validate `attributes` against the category's attribute definitions.

    - Unknown keys   -> error (strict)
    - Missing required defs -> error
    - Type check per def
    """
    defs: dict[str, CategoryAttributeDefinition] = {
        d.key: d for d in category.attribute_definitions.all()
    }

    for key, definition in defs.items():
        if definition.required and key not in attributes:
            raise ValidationError({key: "This attribute is required."})

    for key, value in attributes.items():
        if key not in defs:
            raise ValidationError({key: "Unknown attribute for this category."})
        d = defs[key]

        if d.type == AttributeType.TEXT:
            if not isinstance(value, str):
                raise ValidationError({key: "Must be a string."})
        elif d.type == AttributeType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValidationError({key: "Must be an integer."})
        elif d.type == AttributeType.DECIMAL:
            if not isinstance(value, int | float | str):
                raise ValidationError({key: "Must be a number."})
        elif d.type == AttributeType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValidationError({key: "Must be a boolean."})
        elif d.type == AttributeType.ENUM:
            if value not in d.options:
                raise ValidationError({key: f"Must be one of: {', '.join(map(str, d.options))}."})
    return attributes


@transaction.atomic
def create_product(*, store, actor, data: dict) -> Product:
    category = data["category"]
    attributes = data.get("attributes") or {}
    validate_attributes(category=category, attributes=attributes)

    if data["type"] == ProductType.DIGITAL_PATTERN and data.get("weight_g"):
        raise ValidationError({"weight_g": "Digital products cannot have weight."})

    product = Product.objects.create(
        store=store,
        type=data["type"],
        category=category,
        name=data["name"],
        slug=data["slug"],
        description=data.get("description", ""),
        base_price_cents=data["base_price_cents"],
        currency=data.get("currency", "SEK"),
        tax_class=data.get("tax_class", "STANDARD"),
        weight_g=data.get("weight_g"),
        dimensions=data.get("dimensions") or {},
        attributes=attributes,
        is_active=data.get("is_active", True),
        published_at=data.get("published_at"),
    )

    log_action(
        action="product.created",
        actor=actor,
        target_type="product",
        target_id=product.id,
        metadata={"store_id": str(store.id)},
    )
    return product


@transaction.atomic
def update_product(*, product: Product, actor, data: dict) -> Product:
    if "category" in data:
        validate_attributes(
            category=data["category"],
            attributes=data.get("attributes", product.attributes),
        )
    elif "attributes" in data:
        validate_attributes(category=product.category, attributes=data["attributes"])

    for field in (
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
    ):
        if field in data:
            setattr(product, field, data[field])
    product.save()

    log_action(
        action="product.updated",
        actor=actor,
        target_type="product",
        target_id=product.id,
    )
    return product


@transaction.atomic
def delete_product(*, product: Product, actor) -> None:
    store_id = product.store_id
    product_id = product.id
    product.delete()
    log_action(
        action="product.deleted",
        actor=actor,
        target_type="product",
        target_id=product_id,
        metadata={"store_id": str(store_id)},
    )
