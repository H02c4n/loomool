import uuid

from django.db import models


class AuditLog(models.Model):
    """
    Append-only audit trail.

    `actor_user_id` is a plain UUID (not a ForeignKey) so the trail survives
    user deletion. `actor_email` is a snapshot taken at write time.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_user_id = models.UUIDField(null=True, blank=True)
    actor_email = models.EmailField(blank=True)

    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "audit log entry"
        verbose_name_plural = "audit log entries"
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["actor_user_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at.isoformat()}"
