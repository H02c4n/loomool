from django.conf import settings
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVectorField,
    TrigramSimilarity,
)
from django.db import connection
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import Category, Product, ProductType
from apps.common.csrf import enforce_csrf as _enforce_csrf
from apps.shop import services
from apps.shop.api.serializers import (
    CancelOrderSerializer,
    CartAddItemSerializer,
    CartItemDetailSerializer,
    CartUpdateItemSerializer,
    FavoriteAddSerializer,
    FavoriteSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    PublicProductDetailSerializer,
    PublicProductListSerializer,
    PublicStoreSerializer,
)
from apps.shop.models import Cart, Favorite, Order
from apps.stores.models import Store


class ShopPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 60


def _descendant_category_ids(root_id) -> list:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE tree AS (
                SELECT id FROM catalog_category WHERE id = %s
                UNION ALL
                SELECT c.id FROM catalog_category c
                JOIN tree t ON c.parent_id = t.id
            )
            SELECT id FROM tree
            """,
            [root_id],
        )
        return [row[0] for row in cursor.fetchall()]


def _apply_filters(qs, request):
    category_slug = request.query_params.get("category")
    if category_slug:
        root = Category.objects.active().filter(slug=category_slug).first()
        if root is None:
            return qs.none()
        ids = _descendant_category_ids(root.id)
        qs = qs.filter(category_id__in=ids)

    ptype = request.query_params.get("type")
    if ptype in ProductType.values:
        qs = qs.filter(type=ptype)

    min_p = request.query_params.get("min_price_cents")
    if min_p:
        try:
            qs = qs.filter(base_price_cents__gte=int(min_p))
        except ValueError:
            pass

    max_p = request.query_params.get("max_price_cents")
    if max_p:
        try:
            qs = qs.filter(base_price_cents__lte=int(max_p))
        except ValueError:
            pass

    in_stock = request.query_params.get("in_stock", "").lower() in ("1", "true")
    if in_stock:
        qs = qs.filter(
            variants__is_active=True,
            variants__inventory__quantity_available__gt=0,
        ).distinct()

    return qs


def _apply_sort(qs, request, *, has_search: bool):
    sort = request.query_params.get("sort", "")
    if sort == "price_asc":
        return qs.order_by("base_price_cents", "id")
    if sort == "price_desc":
        return qs.order_by("-base_price_cents", "id")
    if sort == "newest":
        return qs.order_by("-created_at")
    if has_search:
        return qs  # rank ordering was already applied
    return qs.order_by("-created_at")


def _run_search(qs, q: str):
    if not q:
        return qs, False

    vector = RawSQL("search_vector", [], output_field=SearchVectorField())
    query = SearchQuery(q, config="simple")
    ranked = qs.annotate(rank=SearchRank(vector, query))
    matched = ranked.filter(rank__gt=0.0).order_by("-rank")

    # Trigram fallback only if FTS yields fewer than 5 results.
    if matched.count() >= 5:
        return matched, True

    # Trigram similarity — fuzzy fallback for typos / partial names.
    trgm = (
        qs.annotate(trgm=TrigramSimilarity("name", q) + TrigramSimilarity("description", q) * 0.5)
        .filter(trgm__gt=0.1)
        .order_by("-trgm")
    )

    # Combine: FTS first, then trigram (exclude FTS hits from trigram set).
    fts_ids = list(matched.values_list("id", flat=True))
    extra = trgm.exclude(id__in=fts_ids)
    return list(matched) + list(extra), True


@api_view(["GET"])
@permission_classes([AllowAny])
def product_list_view(request):
    """
    Public product listing + search + filter.

    Response headers set Cache-Control for CDN friendliness.
    """
    qs = (
        Product.objects.filter(is_active=True)
        .select_related("store", "category")
        .prefetch_related("images")
    )

    q = (request.query_params.get("q") or "").strip()
    qs = _apply_filters(qs, request)

    if q:
        result, has_search = _run_search(qs, q)
        if isinstance(result, list):
            # Combined FTS + trigram results — paginate manually.
            paginator = ShopPagination()
            page = paginator.paginate_queryset(result, request, view=product_list_view)
            data = PublicProductListSerializer(page, many=True).data
            resp = paginator.get_paginated_response(data)
            resp["Cache-Control"] = "public, max-age=60"
            return resp
        qs = result
    else:
        has_search = False

    qs = _apply_sort(qs, request, has_search=has_search)

    paginator = ShopPagination()
    page = paginator.paginate_queryset(qs, request, view=product_list_view)
    data = PublicProductListSerializer(page, many=True).data
    resp = paginator.get_paginated_response(data)
    resp["Cache-Control"] = "public, max-age=60"
    return resp


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail_view(request, store_slug, product_slug):
    product = get_object_or_404(
        Product.objects.filter(is_active=True)
        .select_related("store", "category")
        .prefetch_related("images", "variants__inventory", "option_definitions"),
        store__slug=store_slug,
        slug=product_slug,
    )
    resp = Response(PublicProductDetailSerializer(product).data)
    resp["Cache-Control"] = "public, max-age=120"
    return resp


@api_view(["GET"])
@permission_classes([AllowAny])
def store_detail_view(request, slug):
    store = get_object_or_404(
        Store.objects.filter(is_active=True).select_related("owner"),
        slug=slug,
    )
    products_qs = (
        Product.objects.filter(store=store, is_active=True)
        .select_related("store", "category")
        .prefetch_related("images")
        .order_by("-created_at")
    )

    paginator = ShopPagination()
    page = paginator.paginate_queryset(products_qs, request, view=store_detail_view)
    payload = {
        "store": PublicStoreSerializer(store).data,
        "products": PublicProductListSerializer(page, many=True).data,
    }
    resp = Response(payload)
    resp["Cache-Control"] = "public, max-age=120"
    return resp


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------


def _serialize_cart(cart):
    if cart is None:
        return {
            "id": None,
            "store_groups": [],
            "total_items": 0,
            "total_cents": 0,
            "currency": "SEK",
        }

    items = (
        cart.items.select_related("variant__product__store", "variant__product__category")
        .prefetch_related("variant__product__images")
        .order_by("variant__product__store__name", "created_at")
    )

    groups: dict = {}
    total_cents = 0
    total_items = 0
    currency = "SEK"

    for item in items:
        product = item.variant.product
        store = product.store
        line_total = item.variant.effective_price_cents * item.quantity
        total_cents += line_total
        total_items += item.quantity
        currency = product.currency

        g = groups.setdefault(
            str(store.id),
            {
                "store": {
                    "id": str(store.id),
                    "slug": store.slug,
                    "name": store.name,
                },
                "items": [],
                "subtotal_cents": 0,
            },
        )
        g["items"].append(CartItemDetailSerializer(item).data)
        g["subtotal_cents"] += line_total

    return {
        "id": str(cart.id),
        "store_groups": list(groups.values()),
        "total_items": total_items,
        "total_cents": total_cents,
        "currency": currency,
    }


def _set_cart_cookie(response, session_key: str):
    response.set_cookie(
        services.CART_SESSION_COOKIE,
        session_key,
        max_age=services.CART_SESSION_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def cart_view(request):
    cart, _ = services.get_or_create_cart_for(request, create=False)
    return Response(_serialize_cart(cart))


@api_view(["POST"])
@permission_classes([AllowAny])
def cart_add_item_view(request):
    if (err := _enforce_csrf(request._request)) is not None:
        return err

    serializer = CartAddItemSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    cart, created = services.get_or_create_cart_for(request, create=True)
    try:
        services.add_item(cart=cart, variant_id=data["variant_id"], quantity=data["quantity"])
    except ValueError as exc:
        return Response({"detail": str(exc.args[0])}, status=status.HTTP_400_BAD_REQUEST)

    resp = Response(_serialize_cart(cart), status=status.HTTP_201_CREATED)
    if created and cart.session_key:
        _set_cart_cookie(resp, cart.session_key)
    return resp


@api_view(["PATCH", "DELETE"])
@permission_classes([AllowAny])
def cart_item_view(request, item_id):
    if (err := _enforce_csrf(request._request)) is not None:
        return err

    cart, _ = services.get_or_create_cart_for(request, create=False)
    if cart is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    item = cart.items.filter(id=item_id).first()
    if item is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        services.remove_item(item=item)
        return Response(_serialize_cart(cart))

    serializer = CartUpdateItemSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        services.update_item(item=item, quantity=serializer.validated_data["quantity"])
    except ValueError:
        return Response({"detail": "invalid_quantity"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_serialize_cart(cart))


@api_view(["DELETE"])
@permission_classes([AllowAny])
def cart_clear_view(request):
    if (err := _enforce_csrf(request._request)) is not None:
        return err
    cart, _ = services.get_or_create_cart_for(request, create=False)
    if cart is not None:
        services.clear_cart(cart=cart)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def favorite_list_view(request):
    qs = (
        Favorite.objects.filter(user=request.user)
        .select_related("product__store")
        .prefetch_related("product__images")
    )
    return Response(FavoriteSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def favorite_toggle_view(request):
    serializer = FavoriteAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        favorite, is_now = services.toggle_favorite(
            user=request.user, product_id=serializer.validated_data["product_id"]
        )
    except ValueError as exc:
        return Response({"detail": str(exc.args[0])}, status=status.HTTP_404_NOT_FOUND)
    if is_now:
        return Response(FavoriteSerializer(favorite).data, status=status.HTTP_201_CREATED)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def order_list_create_view(request):
    """
    GET  — user's orders, newest first.
    POST — create an order from the current cart.

    The cart is derived from the request (user's cart); the client never
    supplies it. Stock reservation is atomic; a failure rolls back the
    entire order including all reservations.
    """
    if request.method == "GET":
        qs = Order.objects.filter(user=request.user).order_by("-created_at")
        return Response(OrderListSerializer(qs, many=True).data)

    cart = Cart.objects.filter(user=request.user).first()
    if cart is None or not cart.items.exists():
        return Response({"detail": "cart_empty"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = services.create_order_from_cart(cart=cart, user=request.user)
    except services.CartEmpty:
        return Response({"detail": "cart_empty"}, status=status.HTTP_400_BAD_REQUEST)
    except services.UnsupportedProductType as exc:
        return Response(
            {
                "detail": "unsupported_product_type",
                "product_type": exc.product_type,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except services.OutOfStock as exc:
        return Response(
            {
                "detail": "out_of_stock",
                "variant_id": str(exc.variant_id),
            },
            status=status.HTTP_409_CONFLICT,
        )

    return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail_view(request, order_id):
    """
    A user can only see their own orders. Any other order id yields 404,
    never 403 — matching the store/product isolation contract.
    """
    order = (
        Order.objects.filter(id=order_id, user=request.user)
        .prefetch_related(
            "seller_orders__items__variant__product__store",
            "seller_orders__store",
        )
        .first()
    )
    if order is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(OrderDetailSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_cancel_view(request, order_id):
    """
    Cancel a PENDING_PAYMENT order and release its stock. Any other
    status → 400 (invalid state). Any other user's order → 404.
    """
    order = Order.objects.filter(id=order_id, user=request.user).first()
    if order is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = CancelOrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        order = services.cancel_order(
            order=order,
            actor=request.user,
            reason=serializer.validated_data.get("reason", "") or "user_cancelled",
        )
    except services.InvalidOrderState as exc:
        return Response(
            {
                "detail": "invalid_order_state",
                "current_status": exc.status,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(OrderDetailSerializer(order).data)
