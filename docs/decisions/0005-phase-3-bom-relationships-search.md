# ADR 0005 — BOM, Relationships, Search Prep

**Date:** Phase 3 Block 3
**Status:** Accepted

## Decisions

| Area | Choice | Why |
| --- | --- | --- |
| BOM component type | `component_variant.product.type == MATERIAL` | Kits contain materials, not other kits. Cycle impossible by construction. |
| BOM kit type | `kit_variant.product.type == DIY_KIT` | BOM only meaningful for kits. |
| BOM cross-store | Forbidden (same-store only) | Simplifies stock semantics; cross-store kits need multi-seller reservation (Phase 5+). |
| BOM upsert | `get_or_create` + update on conflict | Client sends "add 3 yarn"; second request "add 5 yarn" replaces, not appends. Deterministic. |
| Relationships | Free graph, self-reference forbidden, cross-store allowed | Spec 4.6: finished product ↔ kit/pattern/workshop. Cross-store reflects multi-seller reality. |
| Relationship types | `RELATED / COMPLEMENTARY / PATTERN_FOR / KIT_FOR / WORKSHOP_FOR` | Covers spec examples; extensible via choices migration. |
| Search vector | `tsvector` generated column (Postgres) with weights A=name, B=description | Deterministic at write time; no trigger, no Celery. |
| Language config | `simple` (not `swedish`) | Product names are often brand/English; stemming in Swedish can hurt recall. Phase 4 can add per-language columns. |
| Trigram | `pg_trgm` GIN on `name` | Fuzzy match / typo tolerance. |
| Endpoint exposure | Phase 4 | Block 3 only creates schema; no `/search` endpoint yet. |

## Consequences

- Nested kits (kit in kit) not supported. If bundled kits become a requirement, BOM validation needs recursive CTE + cycle check.
- Cross-store BOM rejected at service level. `Product.objects.for_user()` already scopes list endpoints; BOM endpoints additionally validate same store.
- `search_vector` is not in the Django model state. `makemigrations --check` stays clean. Phase 4 can either use `SearchVector` with `RawSQL` or add `GeneratedField` to the model.
- `pg_trgm` extension requires superuser on first creation; `CREATE EXTENSION IF NOT EXISTS` is idempotent. Production must run this during deploy migration (Phase 10 checklist).