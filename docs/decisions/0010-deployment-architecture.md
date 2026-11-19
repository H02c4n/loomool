# ADR 0010 — Deployment Architecture (supersedes D11)

**Date:** Phase 5
**Status:** Accepted (implementation in Phase 10)

## Context

Phase 0 decision D11 was "single VPS, automated DB backups, off-site copy". At start of Phase 5 the deployment target was clarified: **one.com (DNS) + Vercel (frontends) + Render (backend)**. This supersedes D11 and requires a different topology than Docker Compose on one VPS.

## Decisions

| Component | Platform | Notes |
| --- | --- | --- |
| DNS | one.com | A/CNAME records point to Vercel and Render |
| Storefront | Vercel | Next.js project, root `storefront/`; domain `kiterpillar.se` + `www.kiterpillar.se` |
| Seller portal | Vercel | Next.js project, root `seller-portal/`; domain `seller.kiterpillar.se` |
| Backend | Render Web Service | Gunicorn + Django, root `backend/`; domain `api.kiterpillar.se` |
| Celery worker | Render Background Worker | Same repo, `celery -A config worker` |
| Celery beat | Render Background Worker | Same repo, `celery -A config beat` |
| Database | Render PostgreSQL | Managed, daily snapshots |
| Cache / broker | Render Redis | Managed, `/0` cache, `/1` broker, `/2` results |
| Media storage | Cloudflare R2 (or AWS S3 / Backblaze B2) | S3-compatible; MinIO not viable on Render (no persistent disk) |
| SMTP | Postmark / SendGrid (TBD Phase 10) | Domain-verified `kiterpillar.se` |

## Configuration changes required in Phase 10

- `backend/config/settings/production.py`:
  - `SESSION_COOKIE_DOMAIN = ".kiterpillar.se"`
  - `CSRF_COOKIE_DOMAIN = ".kiterpillar.se"`
  - `CORS_ALLOWED_ORIGINS = [...]` — three Vercel origins
  - `CSRF_TRUSTED_ORIGINS = [...]` — same three origins
  - `AWS_S3_ENDPOINT_URL` → R2 endpoint, `AWS_STORAGE_BUCKET_NAME=kiterpillar-media`
- Frontend env: `INTERNAL_API_BASE_URL` and `NEXT_PUBLIC_API_BASE_URL` → `https://api.kiterpillar.se`
- A `render.yaml` in repo root for infrastructure-as-code
- Two Vercel projects with git integration to the same monorepo

## Consequences

- No single VPS to manage; three separate provider dashboards
- MinIO Docker container remains dev-only
- Local Docker Compose continues to work for development
- Rollback strategy per provider (Vercel instant, Render ~1 min)
- Backup strategy shifts to Render PostgreSQL's automated snapshots + manual off-site copy
