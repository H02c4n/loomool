from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from .models import AuditLog


def log_action(
    *,
    action: str,
    actor=None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditLog:
    """
    Append an audit entry.

    Never include passwords, tokens or other secrets in `metadata`.
    Only IDs and non-sensitive contextual flags.
    """
    ip = None
    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = xff.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None

    return AuditLog.objects.create(
        actor_user_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", "") or "",
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else "",
        metadata=metadata or {},
        ip_address=ip,
    )
