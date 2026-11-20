from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path(
        "checkout-sessions/",
        views.create_checkout_session_view,
        name="checkout-session-create",
    ),
    path("webhook/", views.webhook_view, name="webhook"),
]
