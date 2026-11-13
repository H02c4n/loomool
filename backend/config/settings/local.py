from .base import *  # noqa: F403

DEBUG = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

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
