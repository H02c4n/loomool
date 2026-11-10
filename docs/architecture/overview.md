# Loomool — Architecture Overview (Phase 0 → 1)

Source of truth: `mimari-sartname-v2.md` (Bölüm 0–26).

## In one paragraph

Loomool is a multi-seller marketplace for DIY kits, handmade goods, materials and creative workshops. Backend is a modular monolith (Django + DRF + PostgreSQL + Celery/Redis). Two Next.js frontends (`storefront` for customers, `seller-portal` for sellers) consume the same versioned REST API. Financial state is double-entry, immutable and DB-enforced. Phase 1 delivers only the scaffold — no business logic yet.

## Runtime topology (Phase 1)

```
Browser ─┬─► storefront       (Next.js :3000) ─┐
         └─► seller-portal    (Next.js :3001) ─┤
                                               ▼
                                backend (Django :8000) ──► PostgreSQL
                                               │
                                               └─► Redis ─► Celery worker / beat
```

## Module boundaries

Modules do not write to each other's models — they call services (`services.py`). Phase 1 ships only `apps.accounts`. Subsequent phases add `catalog`, `inventory`, `orders`, `payments`, `commissions`, `ledger`, `payouts`, etc., per the spec (Bölüm 3).

## Key decisions carried from Phase 0

- D1 Separate charges and transfers (conditional on Stripe + legal confirmation).
- D4 Double-entry ledger, immutable at DB level.
- D5 Money in minor units (`BIGINT`) + ISO currency code; float forbidden.
- D9 Custom `User` model from day one (this repo: UUID PK, email-only login).
- D11 Single VPS, automated DB backups, off-site copy.
- D14 Mobile after first launch.

See `docs/decisions/` for ADRs.