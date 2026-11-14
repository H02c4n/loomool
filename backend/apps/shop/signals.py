from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from apps.shop import services


@receiver(user_logged_in)
def merge_session_cart_on_login(sender, request, user, **kwargs):
    if request is None:
        return
    session_key = request.COOKIES.get(services.CART_SESSION_COOKIE)
    if session_key:
        services.merge_session_cart(user=user, session_key=session_key)
