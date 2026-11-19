# ADR 0009 — Rebranding: Loomool → Kiterpillar

**Date:** Phase 5
**Status:** Accepted

## Context

Project started as "Loomool" (Phase 0–4). Brand and domain changed to **Kiterpillar** (`kiterpillar.se`) at start of Phase 5. All user-visible text and asset paths must reflect the new brand.

## Decisions

| Area | Change | Notes |
| --- | --- | --- |
| Brand name | Loomool → Kiterpillar | All user-facing copy, metadata, emails |
| Domain | kiterpillar.se | Registered on one.com |
| Slogan | "Make it. Kit it. Sell it." → "Make · Create · Grow" | Matches logo tagline |
| Logo | New SVG assets in `public/brand/kiterpillar-{wordmark,icon,favicon}.svg` | Both storefront and seller-portal |
| Email From | `Kiterpillar <noreply@example.com>` (dev), `noreply@kiterpillar.se` (prod) | `.local` TLD removed — invalid for Django email validation |
| OTP issuer | `Kiterpillar` | TOTP enrollment shows "Kiterpillar" in authenticator apps |
| Celery app name | `kiterpillar` | Task namespace, logs |

## What stays the same

- Docker internal: `POSTGRES_USER=loomool`, `AWS_STORAGE_BUCKET_NAME=loomool-media`, container names `loomool-*`
- GitHub repo: `H02c4n/loomool`
- Local project folder: `~/Desktop/newstart/loomool`
- Historical ADRs 0001–0008: not rewritten (historical record)
- Python package names: `loomool-backend` in `pyproject.toml`, `@loomool/*` in `package.json` → **changed to `@kiterpillar/*`** for frontend packages; Python package name untouched

## Consequences

- Development `.env` needs manual update: `DEFAULT_FROM_EMAIL`, `OTP_TOTP_ISSUER`
- Database user/password unchanged → no migration or volume reset
- S3 bucket name unchanged → no re-upload of existing images
- New logos replace old SVGs; if the old Loomool files remain, they're orphaned and can be deleted
- Phase 6 Stripe account registration should use "Kiterpillar" as business name
