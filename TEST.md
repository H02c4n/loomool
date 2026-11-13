# 1) Env
cp .env.example .env

# 2) pnpm lockfile'ları (CI buna ihtiyaç duyar)
(cd storefront && pnpm install)
(cd seller-portal && pnpm install)

# 3) Ayakta
docker compose up -d --build

# 4) Migration
docker compose exec backend python manage.py migrate

# 5) Health
curl -sS http://localhost:8000/healthz/

# 6) Backend testleri
docker compose exec backend pytest

# 7) Backend lint
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .

# 8) Frontend typecheck + lint + build
docker compose exec storefront pnpm typecheck
docker compose exec storefront pnpm lint
docker compose exec storefront pnpm build
docker compose exec seller-portal pnpm typecheck
docker compose exec seller-portal pnpm lint
docker compose exec seller-portal pnpm build
