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


## Auth flow (Phase 2)

POST /api/v1/auth/register/ → creates CUSTOMER, sends verify email
POST /api/v1/auth/verify-email/ → marks verified
POST /api/v1/auth/login/ → session cookie, cycles session key
GET /api/v1/auth/csrf/ → sets CSRF cookie (SPA)
GET /api/v1/me/ → current user
POST /api/v1/auth/logout/ → CSRF-required, flushes session
POST /api/v1/auth/password-reset/ → always 200 (anti-enumeration)
POST /api/v1/auth/password-reset/confirm/ → sets new password
POST /api/v1/auth/resend-verification/ → 3/h per user


## Seller isolation — three layers (spec 0.2 §3)

1. **Query-level:** `Store.objects.for_user(user)` filters to owned + member stores. Never returns other stores.
2. **Object-level:** `IsStoreMember` / `IsStoreOwner` check `request.user` against the object before serialization.
3. **(future) RLS:** PostgreSQL Row-Level Security as a second safety net for critical tables in Phase 8.

**Contract:** any cross-seller access returns **404**, never 403. This is enforced and tested in `apps/stores/tests/test_isolation_api.py` (CI blocking).



## Catalog (Phase 3)
Category (tree) ── CategoryAttributeDefinition (validation schema)
│
└── Product (store-scoped, JSONB attributes)
├── ProductOptionDefinition
├── ProductVariant ─── Inventory (one row)
├── ProductImage (S3, 3 WebP sizes)
├── ProductComponent (BOM: kit → material)
└── ProductRelationship (graph edges)



**BOM invariant:** `kit.type == DIY_KIT`, `component.type == MATERIAL`, same store, no self-reference. Cycle impossible by construction.

**Search prep:** `catalog_product.search_vector` generated column (name=A, description=B) with GIN + trigram index. Endpoint in Phase 4.

**Isolation:** all mutation endpoints call `Product.objects.for_user(request.user)` and `IsProductStoreMember().has_object_permission()`. Cross-seller access → **404**. BOM additionally enforces same-store for components. Relationships may point cross-store by design.
