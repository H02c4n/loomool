import uuid

from django.db import models


class Inventory(models.Model):
    """
    One row per variant. Reservation primitive is atomic and enforces
    the `available >= 0` invariant at the DB level.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.OneToOneField(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    quantity_available = models.IntegerField(default=0)
    quantity_reserved = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_available__gte=0),
                name="inventory_available_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_reserved__gte=0),
                name="inventory_reserved_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.variant_id}: "
            f"available={self.quantity_available} "
            f"reserved={self.quantity_reserved}"
        )
