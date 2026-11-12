from django.urls import path

from . import views

app_name = "stores"

urlpatterns = [
    path("", views.store_list_view, name="list"),
    path("<uuid:store_id>/", views.store_detail_view, name="detail"),
]
