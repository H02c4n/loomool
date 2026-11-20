"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { createCheckoutSession, fetchOrder } from "@/lib/api";
import { formatSek } from "@/lib/format";
import type { OrderDetail } from "@/lib/types";

type State =
  | { kind: "loading" }
  | { kind: "anonymous" }
  | { kind: "not_found" }
  | { kind: "ready"; order: OrderDetail }
  | { kind: "error"; msg: string };

export default function OrderDetailPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const { orderId } = use(params);
  const [state, setState] = useState<State>({ kind: "loading" });
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const order = await fetchOrder(orderId);
        if (!cancelled) setState({ kind: "ready", order });
      } catch (e) {
        const msg = (e as Error).message;
        if (!cancelled) {
          if (msg === "AUTH_REQUIRED") setState({ kind: "anonymous" });
          else if (msg === "NOT_FOUND") setState({ kind: "not_found" });
          else setState({ kind: "error", msg });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  async function handlePay() {
    setPaying(true);
    setPayError(null);
    try {
      const session = await createCheckoutSession(orderId);
      window.location.href = session.checkout_url;
    } catch (e) {
      setPayError((e as Error).message);
      setPaying(false);
    }
  }

  if (state.kind === "loading") {
    return <p className="empty">Loading…</p>;
  }
  if (state.kind === "anonymous") {
    return (
      <div>
        <p className="empty">Please log in to view this order.</p>
        <Link href="/login" className="btn btn-primary">
          Log in
        </Link>
      </div>
    );
  }
  if (state.kind === "not_found") {
    return <p className="empty">Order not found.</p>;
  }
  if (state.kind === "error") {
    return <p className="error">{state.msg}</p>;
  }

  const order = state.order;
  const isPending = order.status === "PENDING_PAYMENT";

  return (
    <article className="order-detail">
      <nav className="breadcrumbs">
        <Link href="/orders">Orders</Link>
        <span> / </span>
        <span>Order {order.id.slice(0, 8)}…</span>
      </nav>

      <header className="order-detail__header">
        <h1>Order {order.id.slice(0, 8)}…</h1>
        <div className={`status-badge status-badge--${order.status.toLowerCase()}`}>
          {order.status.replace("_", " ")}
        </div>
      </header>

      <div className="order-detail__summary">
        <p>
          <strong>Total:</strong> {formatSek(order.total_cents, order.currency)}
        </p>
        <p>
          <strong>Created:</strong>{" "}
          {new Date(order.created_at).toLocaleString("sv-SE")}
        </p>
        {isPending && (
          <p>
            <strong>Expires:</strong>{" "}
            {new Date(order.expires_at).toLocaleString("sv-SE")}
          </p>
        )}
        {order.payment_status && (
          <p>
            <strong>Payment:</strong> {order.payment_status}
          </p>
        )}
      </div>

      {isPending && order.can_pay && (
        <div className="order-detail__actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handlePay}
            disabled={paying}
          >
            {paying ? "Redirecting…" : "Pay now"}
          </button>
          {payError && <p className="error">{payError}</p>}
        </div>
      )}

      {order.seller_orders.map((so) => (
        <section key={so.id} className="seller-order">
          <header className="seller-order__header">
            <Link href={`/stores/${so.store_slug}`}>
              <strong>{so.store_name}</strong>
            </Link>
            <span className={`status-badge status-badge--${so.status.toLowerCase()}`}>
              {so.status.replace("_", " ")}
            </span>
            <span className="seller-order__subtotal">
              {formatSek(so.subtotal_cents, so.currency)}
            </span>
          </header>
          <ul className="seller-order__items">
            {so.items.map((it) => (
              <li key={it.id} className="order-item">
                <div className="order-item__name">
                  <Link href={`/products/${it.store_slug}/${it.product_slug}`}>
                    {it.product_name}
                  </Link>
                  <span className="order-item__sku">{it.variant_sku}</span>
                </div>
                <div className="order-item__qty">× {it.quantity}</div>
                <div className="order-item__line">
                  {formatSek(it.line_total_cents, so.currency)}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}
