from django.urls import path

from . import views

app_name = "shop"

urlpatterns = [
    path("products/", views.product_list_view, name="product-list"),
    path(
        "products/<slug:store_slug>/<slug:product_slug>/",
        views.product_detail_view,
        name="product-detail",
    ),
    path("stores/<slug:slug>/", views.store_detail_view, name="store-detail"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/items/", views.cart_add_item_view, name="cart-add-item"),
    path("cart/items/<uuid:item_id>/", views.cart_item_view, name="cart-item"),
    path("cart/clear/", views.cart_clear_view, name="cart-clear"),
    path("favorites/", views.favorite_list_view, name="favorite-list"),
    path("favorites/toggle/", views.favorite_toggle_view, name="favorite-toggle"),
    path("orders/", views.order_list_create_view, name="order-list"),
    path("orders/<uuid:order_id>/", views.order_detail_view, name="order-detail"),
    path(
        "orders/<uuid:order_id>/cancel/",
        views.order_cancel_view,
        name="order-cancel",
    ),
]
