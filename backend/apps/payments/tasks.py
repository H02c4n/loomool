import logging

from django.db import transaction
from django.utils import timezone

from apps.payments.models import PaymentEvent
from apps.payments.webhook_handlers import handle_event
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.payments.tasks.retry_failed_payment_events_task")
def retry_failed_payment_events_task() -> dict:
    """
    Retry events whose handler crashed on the first attempt.

    Bounded to 500 rows per tick to protect the beat from large backlogs.
    Events older than 3 days are skipped (Stripe retries for up to 3 days;
    anything later is a bug to be investigated manually).
    """
    now = timezone.now()
    cutoff = now - timezone.timedelta(days=3)

    candidate_ids = list(
        PaymentEvent.objects.filter(
            processed_at__isnull=True,
            created_at__gte=cutoff,
        )
        .values_list("id", flat=True)
        .order_by("created_at")[:500]
    )

    retried = 0
    failed = 0
    for pe_id in candidate_ids:
        pe = PaymentEvent.objects.filter(id=pe_id).first()
        if pe is None:
            continue
        try:
            with transaction.atomic():
                # Reload the event from the stored payload (minimised) — the
                # handler works with the fields we kept.
                handle_event(pe.payload)
                pe.processed_at = timezone.now()
                pe.save(update_fields=["processed_at"])
                retried += 1
        except Exception as exc:
            logger.exception("Retry failed for payment event %s: %s", pe_id, exc)
            failed += 1

    return {"retried": retried, "failed": failed, "scanned": len(candidate_ids)}
