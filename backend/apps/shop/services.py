from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log_action
from apps.catalog.models import ProductType, ProductVariant
from apps.inventory.services import (
    MultiReservationFailed,
    release_many,
    reserve_many,
)
from apps.shop.models import (
    Cart,
    CartItem,
    Favorite,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    SellerOrder,
    SellerOrderStatusHistory,
)

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


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


class CartEmpty(Exception):
    pass


class UnsupportedProductType(Exception):
    def __init__(self, product_type: str):
        super().__init__(f"unsupported_product_type:{product_type}")
        self.product_type = product_type


class OutOfStock(Exception):
    def __init__(self, variant_id):
        super().__init__(f"out_of_stock:{variant_id}")
        self.variant_id = variant_id


class InvalidOrderState(Exception):
    def __init__(self, status: str):
        super().__init__(f"invalid_order_state:{status}")
        self.status = status


@transaction.atomic
def create_order_from_cart(*, cart: Cart, user) -> Order:
    """
    Convert a cart into an Order.

    All-or-nothing:
      1. Reserve stock for every line (atomic; variant_id sort order).
      2. Create Order + SellerOrder(s) + OrderItem(s) with price snapshots.
      3. Append status history rows.
      4. Clear the cart.
    Any failure rolls back the entire transaction, including reservations.

    Phase 5 only sells MATERIAL products. DIY_KIT/other types raise
    `UnsupportedProductType` — BOM stock semantics land in Phase 5b.
    """
    items = list(cart.items.select_related("variant__product__store").all())
    if not items:
        raise CartEmpty()

    for item in items:
        if item.variant.product.type != ProductType.MATERIAL:
            raise UnsupportedProductType(item.variant.product.type)

    try:
        reserve_many([{"variant_id": it.variant_id, "quantity": it.quantity} for it in items])
    except MultiReservationFailed as exc:
        raise OutOfStock(exc.failed_variant_id) from exc

    by_store: dict = {}
    for item in items:
        by_store.setdefault(item.variant.product.store_id, []).append(item)

    now = timezone.now()
    ttl_minutes = settings.ORDER_RESERVATION_TTL_MINUTES
    commission_percent = settings.COMMISSION_DEFAULT_RATE_PERCENT
    currency = items[0].variant.product.currency

    order = Order.objects.create(
        user=user,
        status=OrderStatus.PENDING_PAYMENT,
        currency=currency,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    OrderStatusHistory.objects.create(
        order=order,
        from_status="",
        to_status=OrderStatus.PENDING_PAYMENT,
        reason="order_created",
        actor_user_id=user.id,
    )

    grand_total = 0
    for store_id, store_items in by_store.items():
        seller_order = SellerOrder.objects.create(
            order=order,
            store_id=store_id,
            status=OrderStatus.PENDING_PAYMENT,
            currency=currency,
        )
        SellerOrderStatusHistory.objects.create(
            seller_order=seller_order,
            from_status="",
            to_status=OrderStatus.PENDING_PAYMENT,
            reason="order_created",
            actor_user_id=user.id,
        )

        subtotal = 0
        for item in store_items:
            variant = item.variant
            product = variant.product
            unit_price = variant.effective_price_cents
            line_total = unit_price * item.quantity

            OrderItem.objects.create(
                seller_order=seller_order,
                variant=variant,
                product_name=product.name,
                variant_sku=variant.sku,
                variant_options=variant.options,
                unit_price_cents=unit_price,
                quantity=item.quantity,
                line_total_cents=line_total,
                tax_class=product.tax_class,
                tax_rate_percent=25,
                commission_rate_percent=commission_percent,
                commission_rule_version="phase5-default",
            )
            subtotal += line_total

        seller_order.subtotal_cents = subtotal
        seller_order.save(update_fields=["subtotal_cents"])
        grand_total += subtotal

    order.total_cents = grand_total
    order.save(update_fields=["total_cents"])

    cart.items.all().delete()

    log_action(
        action="order.created",
        actor=user,
        target_type="order",
        target_id=order.id,
        metadata={
            "seller_order_count": len(by_store),
            "item_count": len(items),
            "total_cents": grand_total,
        },
    )
    return order


@transaction.atomic
def cancel_order(*, order: Order, actor, reason: str = "") -> Order:
    """
    Cancel a PENDING_PAYMENT order and release its stock.

    Re-fetches the order under `select_for_update` to prevent races with the
    expiry task or a concurrent user cancel. Raises `InvalidOrderState` if
    the order is not in PENDING_PAYMENT.
    """
    order = Order.objects.select_for_update().get(id=order.id)

    if order.status != OrderStatus.PENDING_PAYMENT:
        raise InvalidOrderState(order.status)

    item_refs = list(
        OrderItem.objects.filter(seller_order__order=order).values("variant_id", "quantity")
    )
    release_many(
        [{"variant_id": ref["variant_id"], "quantity": ref["quantity"]} for ref in item_refs]
    )

    previous_status = order.status
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    resolved_reason = reason or "cancelled"
    actor_id = getattr(actor, "id", None)

    for seller_order in order.seller_orders.all():
        prev = seller_order.status
        seller_order.status = OrderStatus.CANCELLED
        seller_order.save(update_fields=["status", "updated_at"])
        SellerOrderStatusHistory.objects.create(
            seller_order=seller_order,
            from_status=prev,
            to_status=OrderStatus.CANCELLED,
            reason=resolved_reason,
            actor_user_id=actor_id,
        )

    OrderStatusHistory.objects.create(
        order=order,
        from_status=previous_status,
        to_status=OrderStatus.CANCELLED,
        reason=resolved_reason,
        actor_user_id=actor_id,
    )

    log_action(
        action="order.cancelled",
        actor=actor,
        target_type="order",
        target_id=order.id,
        metadata={"reason": resolved_reason},
    )
    return order


# ---------------------------------------------------------------------------
# Payment → order state transition
# ---------------------------------------------------------------------------


@transaction.atomic
def mark_order_paid(*, order, actor, reason: str = "") -> Order:
    """
    Transition a PENDING_PAYMENT order to PAID.

    Called by the Stripe webhook handler when the payment succeeds. Uses
    `select_for_update` so a concurrent cancel or expiry cannot interleave.
    Raises `InvalidOrderState` if the order is not PENDING_PAYMENT — the
    webhook handler treats this as a late payment and logs it.
    """
    order = Order.objects.select_for_update().get(id=order.id)

    if order.status != OrderStatus.PENDING_PAYMENT:
        raise InvalidOrderState(order.status)

    previous_status = order.status
    order.status = OrderStatus.PAID
    order.save(update_fields=["status", "updated_at"])

    actor_id = getattr(actor, "id", None)
    resolved_reason = reason or "payment_succeeded"

    for seller_order in order.seller_orders.select_for_update().all():
        prev = seller_order.status
        seller_order.status = OrderStatus.PAID
        seller_order.save(update_fields=["status", "updated_at"])
        SellerOrderStatusHistory.objects.create(
            seller_order=seller_order,
            from_status=prev,
            to_status=OrderStatus.PAID,
            reason=resolved_reason,
            actor_user_id=actor_id,
        )

    OrderStatusHistory.objects.create(
        order=order,
        from_status=previous_status,
        to_status=OrderStatus.PAID,
        reason=resolved_reason,
        actor_user_id=actor_id,
    )

    log_action(
        action="order.paid",
        actor=actor,
        target_type="order",
        target_id=order.id,
        metadata={"reason": resolved_reason},
    )
    return order
