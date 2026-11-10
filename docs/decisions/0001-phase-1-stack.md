# ADR 0001 — Phase 1 Stack

**Date:** Phase 1 kickoff
**Status:** Accepted

## Context

Phase 0 defined the architectural approach. Phase 1 needs concrete versions and tooling pinned before any code lands.

## Decisions

| Area | Choice | Why |
| ---- | ------ | --- |
| Python | 3.12 | Matches spec (Bölüm 2.1) and long-term support window. |
| Node | 24.22.0 (pinned in Dockerfile + CI) | Reproducible builds; avoids silent major upgrades. |
| Package manager | pnpm 10 (`packageManager` field) | Disk-efficient monorepo, strict peer graph. |
| Framework | Next.js 15 (App Router) + React 19 | Current stable; App Router matches Phase 4 needs. |
| Backend | Django 5.1 + DRF 3.15 | Spec mandates Django; 5.1 is latest LTS-adjacent. |
| DB driver | psycopg 3 (binary) | Modern, async-ready, simpler than psycopg2. |
| Password hashing | Argon2 (primary), PBKDF2 (fallback) | Memory-hard; Django-recommended default. |
| Testing | pytest + pytest-django + factory_boy | Concise fixtures; spec-agnostic. |
| Lint / format | ruff (check + format) | Single tool, fast. |
| Security lint | bandit + pip-audit + gitleaks | Complement CI. |
| Static typing | mypy off (Phase 1) | Deferred — revisit in Phase 2 with Django plugin. |
| Error tracking | Sentry DSN reserved, SDK not installed | No external vendor wired in scaffold. |
| Celery broker | Redis (db 1) | Matches spec; result backend db 2. |
| Admin path | `DJANGO_ADMIN_PATH` (default `manage/`) | Spec 0.2 §10: not `/admin/`. |
| Tests passed report | Never claimed by author; user runs and reports | Per project rules. |

## Consequences

- Locking versions requires discipline: bump PRs need audit + test.
- Node 24.22.0 pin means CI runners must install that specific version (setup-node supports it).
- Argon2 slows test suite; `config.settings.test` uses MD5 for speed and one test asserts Argon2 config via `override_settings`.