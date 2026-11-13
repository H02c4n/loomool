from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import log_action
from apps.catalog.models import Product, ProductRelationship


@transaction.atomic
def add_relationship(
    *,
    from_product: Product,
    to_product: Product,
    relationship_type: str,
    actor,
) -> ProductRelationship:
    if from_product.id == to_product.id:
        raise ValidationError({"to_product": "Cannot relate a product to itself."})

    rel, created = ProductRelationship.objects.get_or_create(
        from_product=from_product,
        to_product=to_product,
        relationship_type=relationship_type,
    )
    if created:
        log_action(
            action="product.relationship.added",
            actor=actor,
            target_type="product",
            target_id=from_product.id,
            metadata={
                "to_product_id": str(to_product.id),
                "relationship_type": relationship_type,
            },
        )
    return rel


@transaction.atomic
def remove_relationship(*, relationship: ProductRelationship, actor) -> None:
    from_id = relationship.from_product_id
    relationship_id = relationship.id
    relationship.delete()
    log_action(
        action="product.relationship.removed",
        actor=actor,
        target_type="product",
        target_id=from_id,
        metadata={"relationship_id": str(relationship_id)},
    )


def list_relationships(*, from_product):
    return ProductRelationship.objects.filter(from_product=from_product).select_related(
        "to_product"
    )
