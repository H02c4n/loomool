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


# ---------------------------------------------------------------------------
# Multi-reservation — for cart → order conversion
# ---------------------------------------------------------------------------


class MultiReservationFailed(Exception):
    """
    Raised when any reservation in a batch fails.

    Attributes:
        failed_variant_id: which variant caused the failure (for logs/UI).
    """

    def __init__(self, failed_variant_id):
        super().__init__(f"insufficient_stock:{failed_variant_id}")
        self.failed_variant_id = failed_variant_id


def reserve_many(items: list[dict]) -> None:
    """
    Atomically reserve stock for multiple variants.

    `items`: [{"variant_id": UUID, "quantity": int}, ...]

    All-or-nothing: if any reservation fails, the entire transaction rolls
    back. Variants are locked in `variant_id` sort order (per spec 4.5) to
    prevent deadlocks between concurrent orders that share variants.
    """
    if not items:
        return

    for it in items:
        if it["quantity"] <= 0:
            raise ValueError("quantity must be positive")

    ordered = sorted(items, key=lambda it: str(it["variant_id"]))

    with transaction.atomic():
        for it in ordered:
            updated = Inventory.objects.filter(
                variant_id=it["variant_id"],
                quantity_available__gte=it["quantity"],
            ).update(
                quantity_available=F("quantity_available") - it["quantity"],
                quantity_reserved=F("quantity_reserved") + it["quantity"],
            )
            if updated == 0:
                # CHECK constraint is the second safety net; raise here so the
                # caller gets a clean exception instead of a DB error.
                raise MultiReservationFailed(it["variant_id"])


def release_many(items: list[dict]) -> None:
    """
    Atomically release stock for multiple variants.

    Symmetric to `reserve_many`. All-or-nothing.
    """
    if not items:
        return

    for it in items:
        if it["quantity"] <= 0:
            raise ValueError("quantity must be positive")

    ordered = sorted(items, key=lambda it: str(it["variant_id"]))

    with transaction.atomic():
        for it in ordered:
            updated = Inventory.objects.filter(
                variant_id=it["variant_id"],
                quantity_reserved__gte=it["quantity"],
            ).update(
                quantity_available=F("quantity_available") + it["quantity"],
                quantity_reserved=F("quantity_reserved") - it["quantity"],
            )
            if updated == 0:
                raise ValueError(f"cannot release more than reserved for {it['variant_id']}")
