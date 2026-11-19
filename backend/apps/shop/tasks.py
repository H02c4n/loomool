import logging

from django.utils import timezone

from apps.shop.models import Order, OrderStatus
from apps.shop.services import InvalidOrderState, cancel_order
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.shop.tasks.expire_stale_orders_task")
def expire_stale_orders_task() -> dict:
    """
    Cancel PENDING_PAYMENT orders past `expires_at` and release their stock.

    Idempotent:
      - `cancel_order` re-checks status under `select_for_update`, so a
        concurrent user cancel or a double task run is safe (the second
        caller raises `InvalidOrderState` and is counted as skipped).
      - Bounded batch (500) so one large backlog cannot block the beat tick.
    """
    now = timezone.now()
    candidate_ids = list(
        Order.objects.filter(
            status=OrderStatus.PENDING_PAYMENT,
            expires_at__lt=now,
        ).values_list("id", flat=True)[:500]
    )

    expired = 0
    skipped = 0
    for order_id in candidate_ids:
        try:
            order = Order.objects.get(id=order_id)
            cancel_order(order=order, actor=None, reason="expired")
            expired += 1
        except InvalidOrderState:
            skipped += 1
        except Exception as exc:
            logger.exception("expire_stale_orders_task failed for order %s: %s", order_id, exc)

    return {"expired": expired, "skipped": skipped}
