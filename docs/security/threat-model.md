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