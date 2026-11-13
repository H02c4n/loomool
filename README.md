# loomool

Marketplace for DIY kits, handmade goods and creative workshops.

**Stack (Phase 1):** Django 5.1 + DRF · PostgreSQL 16 · Redis 7 · Celery 5.4 · Next.js 15 · pnpm · Python 3.12 · Node 24.22.

This repository is the monorepo. Phase 1 is the scaffold: no business logic yet.

## First-time setup

```bash
cp .env.example .env
# edit SECRET_KEY at minimum

# generate pnpm lockfiles — required before CI will pass
(cd storefront && pnpm install)
(cd seller-portal && pnpm install)

docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Services:

| Service       | URL                       |
| ------------- | ------------------------- |
| Backend       | http://localhost:8000     |
| Health        | http://localhost:8000/healthz/ |
| Storefront    | http://localhost:3000     |
| Seller portal | http://localhost:3001     |

Admin path is `DJANGO_ADMIN_PATH` (default `manage/`, not `/admin/`).

## Tests

```bash
docker compose exec backend pytest
```

Tests are written but the author does not report pass/fail — run locally and capture the output.

## Scope discipline

Phase 1 only. Phase 2 (auth endpoints, seller isolation) requires explicit approval.
