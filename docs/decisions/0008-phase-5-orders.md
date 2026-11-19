# ADR 0008 — Phase 5 Orders

**Date:** Phase 5
**Status:** Accepted

## Context

Phase 5 delivers multi-seller order creation from cart, stock reservation, order status history, and an expiry mechanism. Payment (Stripe) is Phase 6.

## Decisions

| Area | Choice | Why |
| --- | --- | --- |
| Order lifecycle | `PENDING_PAYMENT` → `CANCELLED` (Phase 5). Full 11-status enum in place for Phase 6+. | Payment is Phase 6; Phase 5 must not invent money states. |
| Stock reservation | `reserve_many` (atomic multi) — conditional UPDATE per variant in `variant_id` sort order | Spec 4.5 deadlock rule; all-or-nothing |
| Reservation TTL | `ORDER_RESERVATION_TTL_MINUTES=30` (env) | User-facing window; adjustable per environment |
| Expiry task | Celery beat every 60s, bounded batch 500 | Idempotent via `cancel_order`'s `select_for_update` |
| Multi-seller split | `Order` + `SellerOrder` + `OrderItem` | Spec 6.1 explicitly requires seller sub-orders |
| Parent status | Cached column, recomputed on transitions; source of truth = seller orders | Spec 6.1 "ana sipariş durumu, alt siparişlerin durumundan türetilir" |
| Price snapshot | Frozen at creation on `OrderItem` (unit, line, tax, commission) | Spec 6.2 |
| Commission | `commission_rate_percent=COMMISSION_DEFAULT_RATE_PERCENT`, `commission_rule_version="phase5-default"` | Spec 8.2 snapshot; Phase 8 adds CommissionVersion table |
| DIY_KIT orders | **Rejected in Phase 5** (`UnsupportedProductType`) | BOM stock semantics (spec 4.5) need multi-component atomic reservation, deferred to Phase 5b |
| Cart clear | On order creation, atomic with the rest | User intent expressed; re-usable cart not needed |
| Cancel authority | Only owner, only `PENDING_PAYMENT` | Stock released atomically; other states handled in later phases |
| Expired order | Status `CANCELLED`, reason `expired` | Distinguishes from user cancel for reporting |
| Status history | `OrderStatusHistory` + `SellerOrderStatusHistory`, append-only (DB trigger blocks UPDATE/DELETE) | Matches audit log pattern (Phase 2) |
| Audit | `order.created`, `order.cancelled` | Both append-only; DB triggers block UPDATE/DELETE |
| Order total | Cached `total_cents` = sum of seller subtotals | Prices frozen; cache safe |
| Shipping address | `Order.shipping_address` JSONB `{}` placeholder | Phase 6 fills from Stripe Checkout |

## Consequences

- Phase 5 doesn't move money; every order goes to `PENDING_PAYMENT` and stays there until Phase 6 introduces Stripe. Expiry keeps stock from being held forever.
- DIY_KIT variants remain unorderable until Phase 5b, which will extend `create_order_from_cart` with BOM-aware stock resolution and a separate `quantity_available` derivation for kits.
- `Order.total_cents` is denormalized. A future refund/partial-ship workflow must update it consistently or recompute from items; Phase 6 will revisit.
- `Order.status` cache can drift if a code path forgets to call `recompute_status()`. Phase 5 only sets it in `cancel_order` and `create_order_from_cart`; test asserts consistency. Phase 6 adds more transitions and will need a helper pattern.
- `shipping_address` is JSONB `{}` placeholder. Phase 6 will fill it from Stripe Checkout.
- `cancel_order` uses `select_for_update` to race-proof against the expiry task. Expiry task is bounded to 500 orders/tick to avoid a large backlog blocking beat.
- Order history rows **cannot be deleted** by any code path (cascade delete is also blocked by the DB trigger). GDPR anonymisation in Phase 8 will zero out `actor_user_id` via a new append-only "anonymised" marker row, not by deletion.
