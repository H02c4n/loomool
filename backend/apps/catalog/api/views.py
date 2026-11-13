from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_action
from apps.catalog import bom_service, relationship_service, services
from apps.catalog.image_processing import ImageRejected, process_and_save
from apps.catalog.models import (
    Category,
    Product,
    ProductComponent,
    ProductRelationship,
    ProductVariant,
)
from apps.catalog.permissions import IsProductStoreMember
from apps.stores.models import Store

from .serializers import (
    BOMAddSerializer,
    CategoryDetailSerializer,
    CategoryFlatSerializer,
    CategoryListSerializer,
    ProductComponentSerializer,
    ProductCreateSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductRelationshipSerializer,
    ProductUpdateSerializer,
    RelationshipAddSerializer,
)


def _wants_flat(request) -> bool:
    return request.query_params.get("flat", "").lower() in ("1", "true", "yes")


@api_view(["GET"])
@permission_classes([AllowAny])
def category_list_view(request):
    qs = Category.objects.active().select_related("parent")

    if _wants_flat(request):
        qs = qs.order_by("sort_order", "name")
        return Response(CategoryFlatSerializer(qs, many=True).data)

    roots = qs.filter(parent__isnull=True).order_by("sort_order", "name")
    return Response(CategoryListSerializer(roots, many=True, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def category_detail_view(request, slug):
    qs = Category.objects.active().prefetch_related("attribute_definitions")
    category = get_object_or_404(qs, slug=slug)
    return Response(CategoryDetailSerializer(category).data)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def product_list_create_view(request):
    if request.method == "GET":
        qs = (
            Product.objects.for_user(request.user)
            .select_related("store", "category")
            .order_by("-created_at")
        )
        return Response(
            ProductListSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    # POST — create
    serializer = ProductCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        store = Store.objects.for_user(request.user).get(id=data["store_id"])
    except Store.DoesNotExist:
        return Response(
            {"store_id": "Store not found or not accessible."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        category = Category.objects.active().get(id=data["category_id"])
    except Category.DoesNotExist:
        return Response(
            {"category_id": "Category not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payload = dict(data)
    payload.pop("store_id", None)
    payload.pop("category_id", None)
    payload["category"] = category

    try:
        product = services.create_product(store=store, actor=request.user, data=payload)
    except DjangoValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        # UniqueConstraint violation (store, slug) etc.
        return Response(
            {"detail": "Could not create product."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(ProductDetailSerializer(product).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def product_detail_view(request, product_id):
    product = (
        Product.objects.for_user(request.user)
        .select_related("store", "category")
        .filter(id=product_id)
        .first()
    )
    if product is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if not IsProductStoreMember().has_object_permission(request, None, product):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(ProductDetailSerializer(product).data)

    if request.method == "PATCH":
        serializer = ProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if "category_id" in data:
            try:
                data["category"] = Category.objects.active().get(id=data.pop("category_id"))
            except Category.DoesNotExist:
                return Response(
                    {"category_id": "Category not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            product = services.update_product(product=product, actor=request.user, data=data)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

        return Response(ProductDetailSerializer(product).data)

    # DELETE
    services.delete_product(product=product, actor=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def product_image_upload_view(request, product_id):
    product = Product.objects.for_user(request.user).filter(id=product_id).first()
    if product is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if not IsProductStoreMember().has_object_permission(request, None, product):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return Response(
            {"file": "This field is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        metadata = process_and_save(uploaded_file=uploaded, product_id=product.id)
    except ImageRejected as exc:
        return Response({"file": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    from apps.catalog.models import ProductImage

    image = ProductImage.objects.create(
        product=product,
        variant_id=request.data.get("variant_id") or None,
        alt_text=request.data.get("alt_text", "")[:200],
        sort_order=int(request.data.get("sort_order", 0)),
        **metadata,
    )

    log_action(
        action="product.image.uploaded",
        actor=request.user,
        target_type="product",
        target_id=product.id,
        metadata={"image_id": str(image.id)},
    )

    from .serializers import ProductImageSerializer

    return Response(ProductImageSerializer(image).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------


def _get_own_product(request, product_id):
    """Return product the requester can manage, or None (caller -> 404)."""
    return (
        Product.objects.for_user(request.user).select_related("store").filter(id=product_id).first()
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def bom_list_add_view(request, kit_variant_id):
    kit_variant = (
        ProductVariant.objects.select_related("product__store").filter(id=kit_variant_id).first()
    )
    if kit_variant is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    product = _get_own_product(request, kit_variant.product_id)
    if product is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if not IsProductStoreMember().has_object_permission(request, None, product):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        components = bom_service.list_components(kit_variant=kit_variant)
        return Response(ProductComponentSerializer(components, many=True).data)

    serializer = BOMAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    component_variant = (
        ProductVariant.objects.select_related("product__store")
        .filter(id=data["component_variant_id"])
        .first()
    )
    if component_variant is None:
        return Response(
            {"component_variant_id": "Variant not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        component = bom_service.add_component(
            kit_variant=kit_variant,
            component_variant=component_variant,
            quantity=data["quantity"],
            sort_order=data["sort_order"],
            actor=request.user,
        )
    except DjangoValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

    return Response(ProductComponentSerializer(component).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def bom_component_delete_view(request, kit_variant_id, component_id):
    kit_variant = (
        ProductVariant.objects.select_related("product__store").filter(id=kit_variant_id).first()
    )
    if kit_variant is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    product = _get_own_product(request, kit_variant.product_id)
    if product is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if not IsProductStoreMember().has_object_permission(request, None, product):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    component = ProductComponent.objects.filter(id=component_id, kit_variant=kit_variant).first()
    if component is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    bom_service.remove_component(component=component, actor=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def relationship_list_add_view(request, product_id):
    product = _get_own_product(request, product_id)
    if product is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if not IsProductStoreMember().has_object_permission(request, None, product):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        rels = relationship_service.list_relationships(from_product=product)
        return Response(ProductRelationshipSerializer(rels, many=True).data)

    serializer = RelationshipAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    to_product = Product.objects.filter(id=data["to_product_id"]).first()
    if to_product is None:
        return Response(
            {"to_product_id": "Product not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        rel = relationship_service.add_relationship(
            from_product=product,
            to_product=to_product,
            relationship_type=data["relationship_type"],
            actor=request.user,
        )
    except DjangoValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

    return Response(ProductRelationshipSerializer(rel).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def relationship_delete_view(request, product_id, relationship_id):
    product = _get_own_product(request, product_id)
    if product is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if not IsProductStoreMember().has_object_permission(request, None, product):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    rel = ProductRelationship.objects.filter(id=relationship_id, from_product=product).first()
    if rel is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    relationship_service.remove_relationship(relationship=rel, actor=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)
