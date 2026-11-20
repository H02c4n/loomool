# ADR 0011 — Phase 6 Payments

**Date:** Phase 6
**Status:** Accepted

## Context

Phase 6 delivers Stripe Checkout in test mode: payment flow, webhook handling, `PENDING_PAYMENT → PAID` transition, and admin-initiated full refunds. Real money movement is gated to Phase 10 by spec §25.20 and the open budget/legal questions from Phase 0.

## Decisions

| Area | Choice | Why |
| --- | --- | --- |
| Stripe mode | Test only in Phase 6 | Spec §25.20; no legal/accounting sign-off yet |
| Checkout UI | Stripe hosted Checkout, redirect | Keeps card data out of our backend → SAQ A-EP scope |
| Checkout create idempotency | `idempotency_key=checkout-{payment.id}` | Prevents duplicate sessions if user double-clicks |
| Session reuse | Existing open session returns its URL | Avoids orphan sessions on rapid retries |
| Session expiry | `expires_at = max(now + 31min, order.expires_at)` | Stripe requires ≥30min; 31min buffer avoids race where session is rejected exactly at the floor |
| Webhook auth | `stripe.Webhook.construct_event` with raw body + `STRIPE_WEBHOOK_SECRET` | Only signed events mutate state |
| Webhook idempotency | `PaymentEvent.stripe_event_id` UNIQUE | Stripe retries on non-2xx; duplicate events no-op |
| Webhook failure recovery | `PaymentEvent` insert first (`processed_at=null`), apply in same transaction, then set `processed_at`. Celery beat retries rows older than 1 min, younger than 3 days | Outbox pattern; Stripe's 3-day retry window is upstream safety net |
| Payment success path | Only `checkout.session.completed` (and idempotent fallback `payment_intent.succeeded`) | Success redirect is spoofable; webhook is the source of truth (spec §9.11) |
| `PENDING_PAYMENT → PAID` transition | `mark_order_paid` with `select_for_update` | Races with cancel/expiry are prevented by locking |
| Late payment (order already cancelled) | `Payment.status = SUCCEEDED`, audit log `payment.late_payment`, no order transition | Money arrived but the order is gone; Phase 8 adds automatic refund; Phase 9 admin panel surfaces it |
| Refund scope | **Admin full refund only** | Spec Phase 6: "iade senaryoları doğru çalışmalı" — user-initiated flow is Phase 8 |
| Refund idempotency | `idempotency_key=refund-{payment.id}` + `AlreadyRefunded` check | Prevents duplicate Stripe refunds |
| Refund status source | `PENDING` at creation, `SUCCEEDED` from `charge.refunded` webhook | Single source of truth, matches payment model |
| Webhook payload storage | Minimised snapshot (IDs/statuses only, no PII/card data) | GDPR + threat-model spec 14.2 |
| Frontend success UX | Poll `GET /orders/{id}/` every 2.5s up to 60s | Simple, no WebSocket infra |
| Order status cache | Phase 5 pattern continued; `payment_status` computed from latest `Payment` | Payment status is **derived**, not cached on Order |
| Money movement gates | No real keys, no live-mode Stripe account in Phase 6 | Spec §25.20; Phase 10 opens live |

## Consequences

- Two sources of "did the user pay": `Payment.status` and `Order.status`. Both are set inside the same webhook transaction for the happy path. Late payments can desync — see the late-payment row above.
- `test_webhook.py` mocks `stripe.Webhook.construct_event`; the signature-verification code path is only tested via the `SignatureVerificationError` mock. A real CLI smoke test (Phase 10 checklist) validates the actual signature handling.
- `PaymentEvent.payload` is intentionally lossy — `retry_failed_payment_events_task` cannot reconstruct the original event if the handler needs fields we discarded. Phase 8 will call `stripe.Event.retrieve(pe.stripe_event_id)` on retry.
- No customer records at Stripe — every checkout creates a new PaymentIntent. Phase 10 decides whether to save customers for faster repeat checkout.
- Refund amount is always full. Partial refunds (per-item, per-seller) are Phase 8.
- No chargeback UI — `charge.dispute.created` is received but not yet handled (logged for Phase 8).
- Admin refund action is irreversible from the Django Admin UI; two-step (maker-checker, spec §0.2 rule 11) is Phase 9.
- Tests: 25 payments tests + 4 refund tests. CI blocks on `apps/payments/tests/test_isolation.py`.
