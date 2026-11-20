# Threat Model — Phase 0 Summary

Source: mimari-sartname-v2.md, Bölüm 14.6.

| #  | Threat | Mitigation | Phase |
| -- | ------ | ---------- | ----- |
| T1  | Webhook forgery | Signature verification, raw body, time tolerance | 6 |
| T2  | Webhook replay / out-of-order | `stripe_event_id` UNIQUE, state machine | 6 |
| T3  | Client-supplied amount | Amounts only computed backend-side, from order snapshot | 6 |
| T4  | Double payout | UNIQUE `(seller_id, payout_period_id, currency)`, row lock, idempotency key | 8 |
| T5  | Refund / chargeback after payout | Hold period, reserve, offset from future sales, contract clause | 8 |
| T6  | Payout to unverified seller | KYC + account status gate at payout | 8 |
| T7  | Seller account takeover / IBAN swap | Bank data at Stripe, change delay + notify + MFA | 7 |
| T8  | Fraudulent seller | Seller approval, long hold on first payouts, risk score | 7 |
| T9  | Card testing | Rate limiting, Stripe Radar, bot protection | 6 |
| T10 | Silent ledger mutation | DB-level immutability (trigger / no grants), read-only admin | 8 |
| T11 | Admin account takeover | Mandatory MFA, maker-checker on financial ops | 2/9 |
| T12 | Stripe key leak | Secret manager, restricted keys, rotation, secret scanning | 6 |
| T13 | Rounding errors | Minor units, single rounding rule, tests | 8 |
| T14 | Refund × commission ambiguity | Explicit proportional refund rule | 8 |
| T15 | Reconciliation drift | Daily balance-transaction ↔ ledger compare, alert | 8 |

## Phase 1 scope in this document

Phase 1 addresses the *foundations* of these mitigations:

- T9 (partial): Argon2 hashing, password policy, no default admin path, `DEBUG=False` in prod, HSTS/secure cookies.
- T12 (partial): `.env` never committed, gitleaks in CI and pre-commit, no hardcoded secrets.
- T11 (partial): non-default admin path (`DJANGO_ADMIN_PATH`), MFA added in Phase 2.
- T3 (partial): frontend does not compute money — DRF permissions default to `IsAuthenticated`.
- PII in logs: base `LOGGING` config emits only `%(message)s` at JSON level; controllers must avoid logging request bodies.

Everything else lands in its phase.


## Phase 2 mitigations landed

| Threat | Mitigation | Where |
| --- | --- | --- |
| T11 Admin takeover | Audit log for role/login/logout; admin MFA deferred to Phase 9 | `apps/audit/`, `apps/authentication/api/views.py` |
| T9 Card testing (partial) | Rate limit on login (5/m), register (3/h), reset (5/h IP + 3/h email), resend (3/h user) | `apps/authentication/api/views.py` |
| Session fixation | Django `login()` cycles session key; test asserts | `test_login_logout.py` |
| Email enumeration | Register/reset return identical responses for known and unknown emails | `test_register.py`, `test_password_reset.py` |
| Password brute force | Argon2 + min-length 12 + rate limit per IP | `config/settings/base.py` |
| CSRF on session auth | DRF SessionAuthentication; enforced on authenticated unsafe methods | `test_csrf.py` |
| Cross-seller read/write | `Store.objects.for_user()` + `IsStoreMember`; contract: 404 not 403 | `test_isolation_api.py` (CI blocking) |
| Silent audit tampering | DB trigger rejects UPDATE/DELETE on `audit_auditlog` | `audit/migrations/0001_initial.py` |

## Open follow-ups (not blocking Phase 2)

- Session invalidation on password reset — defer to Phase 3.
- Admin MFA UI — Phase 9.
- Per-account lockout (not just IP) — Phase 6.
- `X-Forwarded-For` trust in production — Phase 10 when Caddy is in place.




## Phase 3 threat mitigations

| Threat | Mitigation | Where |
| --- | --- | --- |
| Malicious file upload (SVG/HTML/script) | Magic-byte rejection for `<svg`, `<?xml`, `<!doctype html`, `<html`; Pillow `verify()`; whitelist JPEG/PNG/WebP; max 10 MB | `apps/catalog/image_processing.py` |
| Image-based XSS (polyglot) | Re-encode via Pillow + strip EXIF via `exif_transpose` + WebP output | `image_processing.py::_open_and_validate`, `_encode_webp` |
| Cross-store product access | `ProductScopedManager.for_user()` + `IsProductStoreMember`; contract 404 not 403 | `test_product_crud.py::TestProduct*Isolation` |
| Cross-store image upload | Same 404 contract on image endpoint | `test_images.py::test_other_seller_cannot_upload` |
| Cross-store BOM injection | Service enforces `kit.store == component.store` | `test_bom.py::test_cross_store_component_rejected` |
| Self-reference BOM / relationship | DB `CHECK` constraints + service validation | `component_self_reference`, `relationship_self_reference` |
| Attribute injection (unknown keys) | `validate_attributes` rejects unknown keys strictly | `catalog/services.py` |
| Price manipulation via client | API accepts cents only; frontend never computes totals; Phase 5 will compute from order snapshot | `test_product_crud.py` |
| Orphan S3 files on DB failure | **Known gap** — reconciler in Phase 7 | — |

**Open follow-ups:**
- CSV/PDF digital products (Phase 11) will need different validation rules.
- BOM nested kits (kit in kit) intentionally unsupported; add recursive check if required.


## Phase 4 mitigations

| Threat | Mitigation | Where |
| --- | --- | --- |
| Cross-origin CSRF | `CSRF_TRUSTED_ORIGINS` in local/prod; `SessionAuthentication` for authenticated; `enforce_csrf` for anonymous cart | `config/settings/*`, `apps/common/csrf.py` |
| Cart IDOR | Cart items fetched from `request.user.cart` or `cart_session` cookie only; cross-user `item_id` → 404 | `test_cart_isolation.py` (CI blocking) |
| Anonymous cart takeover | 32-byte URL-safe key in `HttpOnly`, `SameSite=Lax` cookie, 30d; CSRF required for mutation | `apps/shop/services.py` |
| Cart merge conflict | Quantities sum, capped at 10; session cart deleted on success | `test_cart_merge.py` |
| Image URL leakage | S3 private bucket, 1h signed URLs; list endpoints `Cache-Control: public, max-age=60` | `STORAGES`, `_serialize_cart` |
| Favorite data leak | Auth-only; user filter enforced in view | `test_favorites.py::test_two_users_isolated` |
| Cart price manipulation | Server computes totals from `Variant.effective_price_cents`; client cannot change unit price | `services.py::_serialize_cart` |
| Storefront XSS | Product descriptions rendered as text (no `dangerouslySetInnerHTML`); React auto-escapes | All components |
| Origin bypass in curl smoke tests | curl does not send `Origin`, browser does. Browser smoke required for any state-changing endpoint. | Threat-model note for future |


## Phase 5 threat mitigations

| Threat | Mitigation | Where |
| --- | --- | --- |
| Order IDOR | All order endpoints filter on `user=request.user`; cross-user → 404 (never 403) | `apps/shop/api/views.py`, `test_order_isolation.py` (CI blocking) |
| Cancel IDOR | Cancel endpoint scoped to owner; other user's order id → 404 | `test_order_isolation.py::test_buyer_b_cannot_cancel_a_order` |
| Cancel of non-cancellable order | `cancel_order` checks `status == PENDING_PAYMENT` under `select_for_update` | `test_orders.py::TestOrderCancel::test_cancel_twice_fails` |
| Stock oversell race | `reserve_many` uses `UPDATE ... WHERE quantity_available >= n`; DB `CHECK (quantity_available >= 0)` is second net; variants locked in `variant_id` sort order | `apps/inventory/services.py`, `test_orders.py::test_out_of_stock_rolls_back` |
| Deadlock between concurrent orders | Multi-variant reservations sort by `variant_id` before updating | `reserve_many` |
| Partial order creation | All steps (reserve, order, history, cart clear) in one `transaction.atomic()`; any failure rolls back all reservations | `services.create_order_from_cart` |
| Reservation DoS | `ORDER_RESERVATION_TTL_MINUTES=30`; Celery expiry every 60s; bounded 500/order batch | `apps/shop/tasks.py` |
| Expiry task double-cancel | `cancel_order` uses `select_for_update` + status check; second caller gets `InvalidOrderState` | `tasks.py`, `test_order_expiry.py` |
| Price manipulation at checkout | Server computes totals from `Variant.effective_price_cents` at order time; client never sends amounts | `create_order_from_cart` |
| Price change post-order | `OrderItem.unit_price_cents`, `line_total_cents`, `tax_class`, `commission_rate_percent` frozen at creation | `OrderItem` model, ADR 0008 |
| Order history tampering | DB trigger rejects UPDATE/DELETE on `shop_orderstatushistory` and `shop_sellerorderstatushistory` | `shop/migrations/0003_order_history_trigger.py` |
| Cascade delete bypassing history | Cascade delete of `Order` also triggers the history delete trigger, blocking the whole delete | Verified manually in Phase 5 shell test |
| Cross-seller access to orders | Orders are user-scoped; seller view of orders is Phase 7 (will require `Store`-scoped manager + `SellerOrder` permission) | — |

**Open follow-ups (Phase 6+):**

- Stripe webhook replay → handled in Phase 6 (`stripe_event_id` unique, signature verification).
- Partial refund updates `Order.total_cents` consistently — Phase 6.
- `Order.status` cache drift — Phase 6 adds more transitions and will need a helper pattern with tests.
- DIY_KIT orders (Phase 5b) — BOM-aware stock needs its own race tests.
- Seller-side order access (Phase 7) — must repeat the isolation test pattern from Phase 2/4/5.


## Phase 6 threat mitigations

| Threat | Mitigation | Where |
| --- | --- | --- |
| T1 Webhook forgery | `stripe.Webhook.construct_event(raw_body, sig_header, secret)` — signature required, missing/invalid → 400 | `apps/payments/api/views.py` |
| T2 Webhook replay | `PaymentEvent.stripe_event_id` UNIQUE; duplicate → 200 no-op | `PaymentEvent` model, `test_webhook.py::test_duplicate_event_id_is_idempotent` |
| T3 Client-supplied amount | Server uses `order.total_cents` from DB, never from request | `create_checkout_session` |
| T4 Double checkout session | `idempotency_key=checkout-{payment.id}`; existing open session returned | `test_checkout_session.py::test_reuse_open_session` |
| Success-page spoofing | Order transitions only via webhook, never via success redirect | `test_webhook.py::test_session_completed_transitions_to_paid` |
| T9 Card testing | Stripe Radar (test mode active) + `ratelimit(5/m)` on checkout create | `views.py` |
| Checkout IDOR | `Order.objects.filter(id=..., user=request.user)` → other user's order → 404 | `test_isolation.py` |
| CSRF | `_enforce_csrf` on checkout create; webhook is CSRF-exempt but signature-gated | `views.py` |
| Late payment after cancel | Order remains CANCELLED; `payment.late_payment` audit log; Phase 8 auto-refund | `webhook_handlers.py::_handle_checkout_session_completed` |
| Refund IDOR | Admin action only (Django Admin access required); no user-facing refund endpoint | `admin.py` |
| Duplicate refund | `refund-{payment.id}` idempotency key + `AlreadyRefunded` check | `services.refund_payment` |
| Webhook PII leak | `_minimise_payload` stores IDs/statuses only; no card data, no email | `views.py` |
| Webhook handler crash | Event row insert before handler; `processed_at=null` on crash; Celery beat retries within 3-day window | `tasks.retry_failed_payment_events_task` |
| PCI scope | Hosted Stripe Checkout; card data never touches backend | Stripe Checkout |
| Key leakage | `STRIPE_SECRET_KEY` only in backend env; gitleaks regex `sk_live_`/`sk_test_` in CI | `.gitleaks.toml` |

**Open follow-ups (Phase 8/9/10):**

- `charge.dispute.created` received but not handled — Phase 8 chargeback workflow.
- Partial refund / per-seller refund — Phase 8 with ledger.
- Webhook retry fetches `stripe.Event.retrieve` on original event (Phase 6 retries with minimised payload only) — Phase 8.
- Maker-checker on admin refund action (Django Admin single-admin today) — Phase 9.
- Live mode gate (real keys, live Stripe account, legal sign-off) — Phase 10 per spec §25.20.
