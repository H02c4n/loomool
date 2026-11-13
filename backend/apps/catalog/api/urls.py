from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("categories/", views.category_list_view, name="category-list"),
    path(
        "categories/<slug:slug>/",
        views.category_detail_view,
        name="category-detail",
    ),
    path("products/", views.product_list_create_view, name="product-list"),
    path(
        "products/<uuid:product_id>/",
        views.product_detail_view,
        name="product-detail",
    ),
    path(
        "products/<uuid:product_id>/images/",
        views.product_image_upload_view,
        name="product-image-upload",
    ),
    path(
        "variants/<uuid:kit_variant_id>/bom/",
        views.bom_list_add_view,
        name="bom-list-add",
    ),
    path(
        "variants/<uuid:kit_variant_id>/bom/<uuid:component_id>/",
        views.bom_component_delete_view,
        name="bom-component-delete",
    ),
    path(
        "products/<uuid:product_id>/relationships/",
        views.relationship_list_add_view,
        name="relationship-list-add",
    ),
    path(
        "products/<uuid:product_id>/relationships/<uuid:relationship_id>/",
        views.relationship_delete_view,
        name="relationship-delete",
    ),
]
