from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware


def _dummy_view(request):
    return HttpResponse()


def enforce_csrf(django_request):
    """
    Explicitly run Django's CSRF check on a Django (not DRF) request.

    Needed because DRF's @api_view wrapper sets csrf_exempt=True on the
    outer function, which makes CsrfViewMiddleware skip the check globally.
    Call this at the top of unsafe DRF views that need CSRF (e.g. anonymous
    cart mutations) so the check runs inside the view.

    Returns None on success, HttpResponseForbidden on failure.
    """
    django_request.csrf_processing_done = False
    return CsrfViewMiddleware(_dummy_view).process_view(django_request, _dummy_view, (), {})
