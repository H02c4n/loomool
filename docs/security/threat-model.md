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