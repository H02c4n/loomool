from __future__ import annotations

from django.db import transaction
from django.db.models import F

from .models import Inventory


class InsufficientStock(Exception):
    """Raised when reservation would drive available below zero."""


def reserve(variant_id, quantity: int) -> Inventory:
    """
    Atomically move `quantity` from available to reserved.

    Single UPDATE with a WHERE clause, so no separate SELECT FOR UPDATE is
    needed. Postgres will lock the row, apply the check, and commit — the
    `CHECK (available >= 0)` constraint is the second safety net.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    with transaction.atomic():
        updated = Inventory.objects.filter(
            variant_id=variant_id,
            quantity_available__gte=quantity,
        ).update(
            quantity_available=F("quantity_available") - quantity,
            quantity_reserved=F("quantity_reserved") + quantity,
        )
        if updated == 0:
            raise InsufficientStock()

        return Inventory.objects.get(variant_id=variant_id)


def release(variant_id, quantity: int) -> Inventory:
    """Move `quantity` back from reserved to available."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    with transaction.atomic():
        updated = Inventory.objects.filter(
            variant_id=variant_id,
            quantity_reserved__gte=quantity,
        ).update(
            quantity_available=F("quantity_available") + quantity,
            quantity_reserved=F("quantity_reserved") - quantity,
        )
        if updated == 0:
            raise ValueError("cannot release more than reserved")

        return Inventory.objects.get(variant_id=variant_id)


def consume(variant_id, quantity: int) -> Inventory:
    """Remove `quantity` from reserved (order shipped/paid/complete)."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    with transaction.atomic():
        updated = Inventory.objects.filter(
            variant_id=variant_id,
            quantity_reserved__gte=quantity,
        ).update(quantity_reserved=F("quantity_reserved") - quantity)
        if updated == 0:
            raise ValueError("cannot consume more than reserved")

        return Inventory.objects.get(variant_id=variant_id)


def adjust(variant_id, new_available: int) -> Inventory:
    """Admin-only absolute set of available quantity."""
    if new_available < 0:
        raise ValueError("new_available must be non-negative")
    Inventory.objects.filter(variant_id=variant_id).update(quantity_available=new_available)
    return Inventory.objects.get(variant_id=variant_id)
