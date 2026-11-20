from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production-test-secret-key-not-for-production"
ALLOWED_HOSTS = ["*"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {
    "default": env.db(  # noqa: F405
        "DATABASE_URL",
        "postgresql://loomool:loomool@localhost:5432/loomool",
    )
}
CELERY_TASK_ALWAYS_EAGER = True

# Test-time overrides — no external Redis, no real email
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# In-memory file storage for tests — no MinIO, no S3.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


# Faster reservation expiry for tests. Tests can override per-case.
ORDER_RESERVATION_TTL_MINUTES = 1


# Stripe test doubles — real SDK calls are mocked in tests, but these
# values make `stripe.api_key` truthy so configuration checks pass.
STRIPE_SECRET_KEY = "sk_test_mock_for_tests"
STRIPE_PUBLISHABLE_KEY = "pk_test_mock_for_tests"
STRIPE_WEBHOOK_SECRET = "whsec_test_mock_for_tests"
STRIPE_API_VERSION = "2024-11-20.acacia"
