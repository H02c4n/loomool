# ADR 0004 — Phase 3 Catalog

**Date:** Phase 3
**Status:** Accepted

## Decisions

| Area | Choice | Why |
| --- | --- | --- |
| Category tree | Adjacency list (`parent_id` FK) + recursive cleanup in model save | No extra dependency; 3-level tree well within PostgreSQL CTE capabilities |
| Attribute storage | JSONB on Product, schema in `CategoryAttributeDefinition` | Flexible per category, no migration to add types; strict validation in services |
| Option definitions | `ProductOptionDefinition` + `Variant.options` JSONB | Declarative option set per product; variants carry concrete values |
| BOM | `ProductComponent` (kit_variant, component_variant, qty) | Variant-level: same material can appear in many kits with own stock |
| Inventory | One row per variant, `SELECT ... FOR UPDATE` (via atomic UPDATE) | Spec 4.5 requires atomicity + `CHECK (available >= 0)`; DB constraint enforced |
| Product images | Re-encoded to WebP at 3 sizes, stored in S3 (MinIO local) | Spec 14.3: whitelist + re-encode; S3 for Phase 10 continuity |
| Image upload | Synchronous Pillow processing | Simple and correct; Celery async deferred to Phase 7 if needed |
| Image security | Magic-byte rejection for SVG/HTML, Pillow verify, size cap 10MB, EXIF stripped by re-encode | Spec 14.3 compliance |
| Store scoping | `ProductScopedManager.for_user()` + `IsProductStoreMember` object permission; **contract: 404 not 403** | Spec 0.2 §3 + §4 |
| Slug uniqueness | `(store, slug)` | SEO-friendly per store; Store slug makes public URL globally unique |
| Price | `Product.base_price_cents`, `Variant.price_cents` override (nullable) | Single price location for single-variant; per-variant override when needed |
| Currency | Per product, default SEK | Phase 0 decision; multi-currency expansion via per-product currency, not global |
| Product type | CharField with `ProductType.choices` | Business rules per type live in services; new type = code change, acceptable |

## Consequences

- Attribute validation happens on product create/update. Adding/changing category definitions does **not** retroactively revalidate existing products.
- BOM cycle check (kit A → kit B → kit A) is enforced only at creation in services. Cannot currently create a cycle via API because a kit can only contain `MATERIAL` variants — will be enforced when BOM API is built in Block 3.
- Image orphan cleanup on failed DB write is **not** implemented; Phase 7 will add a reconciler.
- `Variant.effective_price_cents` is a Python property; filterable via JSONB if needed later.