# ADR 0003 — Phase 2 Auth & Authorization

**Date:** Phase 2
**Status:** Accepted

## Context

Phase 2 delivers registration, login, password reset, email verification,
roles, and seller-store isolation (spec Bölüm 22).

## Decisions

| Area | Choice | Why |
| --- | --- | --- |
| User model | `role` CharField + Django Groups | Primary role for view-level checks; groups for fine-grained permissions in later phases |
| Token storage | DB-backed `EmailVerificationToken`, `PasswordResetToken` | Single-use, revocable, auditable. Plaintext only in email; SHA-256 hash in DB |
| Token TTL | Verify 48h, Reset 2h (env-overridable) | Long enough for users, short enough to limit exposure |
| Authentication | Session cookie (`HttpOnly`, `SameSite=Lax`) | Spec D8 (web). Mobile JWT deferred to Phase 12 |
| Session rotation | Django `login()` cycles session key | Prevents session fixation |
| CSRF | Explicit `_enforce_csrf` helper on register/login/password-reset-request; DRF `SessionAuthentication` on authenticated unsafe methods | `@api_view` sets `csrf_exempt=True` on its wrapper, so `@csrf_protect` and the global `CsrfViewMiddleware` skip CSRF for all DRF views. The helper calls `CsrfViewMiddleware.process_view` manually inside the view. Token-in-URL endpoints (verify-email, reset-confirm) rely on their one-time token — CSRF adds no protection there. Frontend must GET `/api/v1/auth/csrf/` before those three POSTs. |
| Password policy | Django validators, min 12 chars, Argon2 hash | Argon2 primary; PBKDF2 fallback for legacy hashes |
| Rate limiting | `django-ratelimit` on login, register, reset, resend | Cache: Redis in prod, locmem in test |
| IP key | `REMOTE_ADDR` default; `HTTP_X_FORWARDED_FOR` in production | Behind Caddy/Cloudflare; documented in `config/settings/production.py` |
| Anti-enumeration | Register duplicate → 201 no email; reset unknown → 200 no email | Same response either way |
| Audit | All auth events logged to append-only `AuditLog` | T11 prerequisite; DB trigger blocks UPDATE/DELETE |
| Admin MFA | Not wired in Phase 2 UI; `django-otp` installed; admin login MFA in Phase 9 | Phase 2 only establishes the infrastructure |
| Roles | CUSTOMER default; SUPER_ADMIN data-migrated from `is_superuser=True` | Existing superusers preserved; others default to CUSTOMER |

## Consequences

- Rate limit is IP+key based. Phase 6 will add per-account lockout beyond IP.
- CSRF for anonymous endpoints is deliberate; changing it requires deliberate decision (test guards it).
- Admin MFA UI deferred; Phase 9 will wire `django-otp` into admin login.
- Session invalidation on password reset (other devices) deferred to Phase 3 improvement.
- CSRF is enforced on register/login/password-reset-request via `@csrf_protect` (Django view-level). All other endpoints rely on DRF `SessionAuthentication`'s built-in CSRF enforcement, which only fires for authenticated requests. Frontend must GET `/api/v1/auth/csrf/` before those three POSTs; the CSRF cookie is HttpOnly-safe (not HttpOnly, so the SPA can read it).
