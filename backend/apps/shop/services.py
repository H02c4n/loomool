from __future__ import annotations

import secrets

from django.db import transaction

from apps.catalog.models import ProductVariant
from apps.shop.models import Cart, CartItem, Favorite

CART_SESSION_COOKIE = "cart_session"
CART_SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
CART_ITEM_MAX_QUANTITY = 10


def get_or_create_cart_for(request, *, create: bool) -> tuple[Cart | None, bool]:
    """
    Resolve the requester's cart.

    Authenticated  -> user cart, created if missing.
    Anonymous      -> cart by cart_session cookie if present.
                      If create and no cart, create one; caller must set
                      the Set-Cookie header on the response.

    Returns (cart, was_created). `cart` may be None when create=False and
    the requester has no cart (e.g. GET /cart/ for a fresh anonymous user).
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart, False

    session_key = request.COOKIES.get(CART_SESSION_COOKIE)
    if session_key:
        cart = Cart.objects.filter(session_key=session_key).first()
        if cart is not None:
            return cart, False

    if not create:
        return None, False

    session_key = secrets.token_urlsafe(32)
    cart = Cart.objects.create(session_key=session_key)
    return cart, True


def add_item(*, cart: Cart, variant_id, quantity: int) -> CartItem:
    variant = (
        ProductVariant.objects.select_related("product")
        .filter(id=variant_id, is_active=True, product__is_active=True)
        .first()
    )
    if variant is None:
        raise ValueError("variant_not_found")

    with transaction.atomic():
        item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart, variant=variant, defaults={"quantity": quantity}
        )
        if not created:
            item.quantity = min(item.quantity + quantity, CART_ITEM_MAX_QUANTITY)
            item.save(update_fields=["quantity"])
    return item


def update_item(*, item: CartItem, quantity: int) -> CartItem:
    if quantity < 1 or quantity > CART_ITEM_MAX_QUANTITY:
        raise ValueError("invalid_quantity")
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    return item


def remove_item(*, item: CartItem) -> None:
    item.delete()


def clear_cart(*, cart: Cart) -> None:
    cart.items.all().delete()


@transaction.atomic
def merge_session_cart(*, user, session_key: str) -> None:
    """
    Merge an anonymous session cart into the user's cart.

    Collisions on (variant) sum quantities, capped at CART_ITEM_MAX_QUANTITY.
    The session cart is deleted on success.
    """
    session_cart = Cart.objects.select_for_update().filter(session_key=session_key).first()
    if session_cart is None:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)

    for item in session_cart.items.all():
        existing = user_cart.items.filter(variant_id=item.variant_id).first()
        if existing is not None:
            existing.quantity = min(existing.quantity + item.quantity, CART_ITEM_MAX_QUANTITY)
            existing.save(update_fields=["quantity"])
        else:
            item.cart = user_cart
            item.save(update_fields=["cart"])
    session_cart.delete()


def toggle_favorite(*, user, product_id) -> tuple[Favorite, bool]:
    """
    Toggle a favorite. Returns (favorite, is_now_favorited).

    If the favorite exists, it's removed and (None, False) is returned.
    If it doesn't exist, it's created and (Favorite, True) is returned.
    """
    from apps.catalog.models import Product

    product = Product.objects.filter(id=product_id, is_active=True).first()
    if product is None:
        raise ValueError("product_not_found")

    existing = Favorite.objects.filter(user=user, product=product).first()
    if existing is not None:
        existing.delete()
        return None, False

    favorite = Favorite.objects.create(user=user, product=product)
    return favorite, True
