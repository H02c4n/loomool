import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    """
    Rate limits are per-IP / per-user via Django cache. Without a reset,
    test N+1 hits the limit set by tests 1..N. Clear before and after.
    """
    cache.clear()
    yield
    cache.clear()
