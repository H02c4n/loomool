"""
Thin wrapper around the Stripe SDK.

- Lazily configures `stripe.api_key` from settings (tests override the key).
- Centralises the version pin so all calls use the same API contract.
- Never imported at module load; call `client()` to access the configured SDK.
"""

from __future__ import annotations

from django.conf import settings


class StripeNotConfigured(Exception):
    """STRIPE_SECRET_KEY is empty — production misconfiguration."""


def _configure():
    if not settings.STRIPE_SECRET_KEY:
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set; payments are disabled.")

    import stripe  # local import — avoids import-time side effects in tests

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = settings.STRIPE_API_VERSION
    return stripe


def client():
    """Return the configured `stripe` module."""
    return _configure()


def webhook():
    """Return the `stripe.Webhook` helper (signature verification)."""
    return _configure().Webhook
