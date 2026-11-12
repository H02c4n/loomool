from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("me/", views.me_view, name="me"),
]
