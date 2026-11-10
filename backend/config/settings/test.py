from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production-test-secret-key-not-for-production"
ALLOWED_HOSTS = ["*"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {
    "default": env.db(  # noqa: F405
        "DATABASE_URL",
        default="postgresql://loomool:loomool@localhost:5432/loomool",
    )
}
CELERY_TASK_ALWAYS_EAGER = True
