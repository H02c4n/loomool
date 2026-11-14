from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS as _BASE_ALLOWED_HOSTS

DEBUG = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Docker-internal hostname `backend` for Next.js SSR.
# Production behind Caddy uses real domains (config/settings/production.py).
ALLOWED_HOSTS = [*_BASE_ALLOWED_HOSTS, "backend"]

# SPA dev servers on :3000 and :3001 are different origins from the backend
# on :8000. Django's CSRF checks the Origin header — trust the SPA origins
# locally only; production uses real domains.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
]

# Local dev uses MinIO (see docker-compose.yml). The bucket must exist;
# create it once with: docker compose exec minio mc mb /data/loomool-media
STORAGES["default"]["OPTIONS"].update(  # noqa: F405
    {
        "endpoint_url": env(  # noqa: F405
            "AWS_S3_ENDPOINT_URL", default="http://minio:9000"
        ),
        "access_key": env("AWS_ACCESS_KEY_ID", default="loomool"),  # noqa: F405
        "secret_key": env(  # noqa: F405
            "AWS_SECRET_ACCESS_KEY", default="loomool-minio-dev"
        ),
        "region_name": env("AWS_S3_REGION_NAME", default="us-east-1"),  # noqa: F405
    }
)
