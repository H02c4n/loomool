# ADR 0006 — Phase 4 Shop (Public Catalog)

**Date:** Phase 4 Block 1
**Status:** Accepted

## Decisions

| Area | Choice | Why |
| --- | --- | --- |
| API namespace | New `apps.shop` at `/api/v1/shop/` | Separate permission model, serializer, audit, cache from seller-facing `catalog/` |
| Product URL | `/api/v1/shop/products/<store_slug>/<product_slug>/` | SEO-friendly; unique per (store, slug) already enforced in Phase 3 |
| Search | `search_vector` FTS (A=name, B=description) with `SearchRank`; trigram fallback if <5 FTS hits | Deterministic ranking; trigram covers typos |
| Search config | `simple` (not `swedish`) | Phase 3 decision — brand names are mostly English |
| Filters | category (recursive CTE, descendants included), type, min/max price (base), in_stock | Covers Phase 4 spec 11; `Variant`-level price filter deferred |
| Sort | `relevance` (when `q`), `price_asc`, `price_desc`, `newest` | Every listing has a sensible default; no sort → newest |
| Pagination | `page` / `page_size` (20 default, 60 max) via DRF PageNumber | SSR-friendly for Next.js; cursor may come in Phase 5+ |
| Cache | `Cache-Control: public, max-age=60` on lists; `120` on detail/store | CDN-friendly; invalidated by cache-bust on write — safe because writes rare in Phase 4 |
| Image serving | S3 signed URLs, `AWS_QUERYSTRING_AUTH=True`, 3600s expiry (Soru 3=A) | Private bucket; works with local MinIO and production S3 |
| Store page | `GET /api/v1/shop/stores/<slug>/` with paginated active products | Store profile + product list in one call; separate endpoint would cost 2 requests |
| Anonymous access | All public endpoints `AllowAny` | Spec: customer discovery; cart/favorites require session but products do not |
| Cart / Favorites | Deferred to Block 2 | Separation keeps Block 1 reviewable; cart touches inventory semantics |

## Consequences

- `Cache-Control` headers on API responses are safe for anonymous views but will need revalidation when the API becomes user-specific (cart badge in header). Phase 4 UI should fetch cart count from a separate endpoint that is not cached.
- Price filtering uses `Product.base_price_cents`. If a variant overrides price, the filter may miss edge cases. Phase 5 will implement `Variant.effective_price_cents` filtering via subquery if needed.
- Trigram fallback is only triggered when FTS returns <5 results. If FTS returns 3 fuzzy hits and 2 typo hits would be better, they won't appear. Acceptable MVP tradeoff.
- Search `Config` is hardcoded `simple`. Per-language (Swedish) search vector is a Phase 5+ consideration.
- `owner_display_name` uses `User.get_full_name()`. Owners who don't set first/last name will show empty string; Phase 7 seller profile will add `display_name`.
