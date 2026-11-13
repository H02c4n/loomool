from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import log_action
from apps.catalog.models import ProductComponent, ProductType


def _validate_kit_and_component(*, kit_variant, component_variant) -> None:
    if kit_variant.product.type != ProductType.DIY_KIT:
        raise ValidationError({"kit_variant": "Kit variant must belong to a DIY_KIT product."})
    if component_variant.product.type != ProductType.MATERIAL:
        raise ValidationError({"component_variant": "Component must belong to a MATERIAL product."})
    if kit_variant.product.store_id != component_variant.product.store_id:
        raise ValidationError(
            {"component_variant": ("Component must belong to the same store as the kit.")}
        )
    if kit_variant.id == component_variant.id:
        raise ValidationError({"component_variant": "Kit cannot contain itself."})


@transaction.atomic
def add_component(
    *,
    kit_variant,
    component_variant,
    quantity: int,
    sort_order: int,
    actor,
) -> ProductComponent:
    if quantity < 1:
        raise ValidationError({"quantity": "Quantity must be at least 1."})

    _validate_kit_and_component(kit_variant=kit_variant, component_variant=component_variant)

    component, created = ProductComponent.objects.get_or_create(
        kit_variant=kit_variant,
        component_variant=component_variant,
        defaults={"quantity": quantity, "sort_order": sort_order},
    )
    if not created:
        component.quantity = quantity
        component.sort_order = sort_order
        component.save(update_fields=["quantity", "sort_order"])

    log_action(
        action="bom.component.set",
        actor=actor,
        target_type="kit_variant",
        target_id=kit_variant.id,
        metadata={
            "component_variant_id": str(component_variant.id),
            "quantity": quantity,
        },
    )
    return component


@transaction.atomic
def remove_component(*, component: ProductComponent, actor) -> None:
    kit_id = component.kit_variant_id
    component_id = component.id
    component.delete()
    log_action(
        action="bom.component.removed",
        actor=actor,
        target_type="kit_variant",
        target_id=kit_id,
        metadata={"component_id": str(component_id)},
    )


def list_components(*, kit_variant):
    return ProductComponent.objects.filter(kit_variant=kit_variant).select_related(
        "component_variant__product"
    )
