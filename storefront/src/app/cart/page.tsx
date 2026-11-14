"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiMutate, fetchCart } from "@/lib/api";
import { formatSek, rewriteMediaUrl } from "@/lib/format";
import type { Cart, CartItem } from "@/lib/types";

export default function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyItemId, setBusyItemId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const c = await fetchCart();
      setCart(c);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function updateQty(item: CartItem, quantity: number) {
    setBusyItemId(item.id);
    setError(null);
    try {
      const updated = await apiMutate<Cart>(
        "PATCH",
        `/api/v1/shop/cart/items/${item.id}/`,
        { quantity }
      );
      if (updated) setCart(updated);
      window.dispatchEvent(new CustomEvent("cart:updated"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyItemId(null);
    }
  }

  async function removeItem(item: CartItem) {
    setBusyItemId(item.id);
    setError(null);
    try {
      const updated = await apiMutate<Cart>(
        "DELETE",
        `/api/v1/shop/cart/items/${item.id}/`
      );
      if (updated) setCart(updated);
      window.dispatchEvent(new CustomEvent("cart:updated"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyItemId(null);
    }
  }

  if (cart === null) {
    return (
      <div className="cart-page">
        <h1>Your cart</h1>
        <p className="empty">Loading…</p>
      </div>
    );
  }

  if (!cart.id || cart.total_items === 0) {
    return (
      <div className="cart-page">
        <h1>Your cart</h1>
        <p className="empty">Your cart is empty.</p>
        <Link href="/search" className="btn btn-primary">
          Browse products
        </Link>
      </div>
    );
  }

  return (
    <div className="cart-page">
      <h1>Your cart</h1>
      {error && <p className="error">{error}</p>}

      {cart.store_groups.map((group) => (
        <section key={group.store.id} className="cart-group">
          <header className="cart-group__header">
            <Link href={`/stores/${group.store.slug}`}>
              <strong>{group.store.name}</strong>
            </Link>
            <span className="cart-group__subtotal">
              {formatSek(group.subtotal_cents, cart.currency)}
            </span>
          </header>

          <ul className="cart-group__items">
            {group.items.map((item) => {
              const thumb = rewriteMediaUrl(item.product.thumb_url);
              const isBusy = busyItemId === item.id;
              return (
                <li key={item.id} className="cart-item">
                  <div className="cart-item__thumb">
                    {thumb ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={thumb} alt={item.product.name} />
                    ) : (
                      <span className="product-card__placeholder">Loomool</span>
                    )}
                  </div>
                  <div className="cart-item__body">
                    <Link
                      href={`/products/${item.product.store_slug}/${item.product.slug}`}
                      className="cart-item__name"
                    >
                      {item.product.name}
                    </Link>
                    <div className="cart-item__sku">{item.variant.sku}</div>
                  </div>
                  <div className="cart-item__qty">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={isBusy || item.quantity <= 1}
                      onClick={() => updateQty(item, item.quantity - 1)}
                    >
                      −
                    </button>
                    <span>{item.quantity}</span>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={isBusy || item.quantity >= 10}
                      onClick={() => updateQty(item, item.quantity + 1)}
                    >
                      +
                    </button>
                  </div>
                  <div className="cart-item__line">
                    {formatSek(item.line_total_cents, cart.currency)}
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={isBusy}
                    onClick={() => removeItem(item)}
                    aria-label="Remove"
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      <footer className="cart-footer">
        <div>
          <strong>Total: {formatSek(cart.total_cents, cart.currency)}</strong>
          <span className="cart-footer__note">
            {" "}
            · {cart.total_items} item{cart.total_items === 1 ? "" : "s"}
          </span>
        </div>
        <button type="button" className="btn btn-primary" disabled>
          Checkout — coming in Phase 5
        </button>
      </footer>
    </div>
  );
}
