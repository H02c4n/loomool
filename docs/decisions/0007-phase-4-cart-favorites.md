# ADR 0007 — Phase 4 Cart & Favorites

**Date:** Phase 4 Block 2
**Status:** Accepted

## Decisions

| Area | Choice | Why |
| --- | --- | --- |
| Cart ownership | One cart per user OR per `session_key`, XOR enforced by CHECK | Device-portable for logged-in users; anonymous visitors still get a cart without registration |
| Anonymous cart identity | `cart_session` cookie, 32-byte URL-safe, `HttpOnly`, `SameSite=Lax`, 30d, `Secure` in prod | Attacker cannot read the key; CSRF still required for mutation |
| Cart merge | On `user_logged_in` signal, session cart merged into user cart | No client-side coordination; works for any login path |
| Merge collision | Quantities sum, cap 10 | User's intent preserved; cap prevents abuse |
| Cart item cap | 1–10 enforced by CHECK | Phase 5 will not place 100-qty orders from a 100-qty cart |
| Cart response | Grouped by store; per-group subtotal + grand total | Phase 5 will split order per store group (spec 6) |
| Cart pricing | `Variant.effective_price_cents` (current) | Order snapshot is Phase 5; cart shows current price, recomputed server-side |
| Favorites | Auth-only, toggle-on-create / toggle-off-delete | Anonymous favorites would require a separate identity; Phase 4 scope |
| CSRF | `enforce_csrf` on anonymous cart mutations; `SessionAuthentication` CSRF for authenticated cart & favorites | API `api_view` bypasses Django CSRF middleware — see ADR 0003 |
| Services refactor | `_enforce_csrf` moved to `apps.common.csrf.enforce_csrf` | Shop needs it; auth imports from common; single source of truth |

## Consequences

- Anonymous cart is orphaned if the user clears cookies before login. Phase 5 adds a Celery cleanup task (`cart.age > 90 days AND user is null`).
- Carts are not currency-agnostic. `cart_summary` returns the currency of the last item iterated. Phase 5 multi-currency order will need per-group currency validation.
- Login-merge is synchronous. With 1-2 items it's sub-millisecond; at large scale Phase 5 may move to Celery.
- `cart_item_quantity_range` CHECK prevents >10. Increment logic clamps silently in `add_item`; PATCH rejects with 400. Consistent, but silent clamping on add is a minor UX quirk.
- Favorites are per-user only. Product favorites on the storefront will require the user to be logged in; anonymous "save" prompt becomes a "log in to save" CTA in the UI.
