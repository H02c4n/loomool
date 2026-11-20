"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchOrders } from "@/lib/api";
import { formatSek } from "@/lib/format";
import type { OrderListItem } from "@/lib/types";

type State =
  | { kind: "loading" }
  | { kind: "anonymous" }
  | { kind: "ready"; items: OrderListItem[] }
  | { kind: "error"; msg: string };

export default function OrdersPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const items = await fetchOrders();
        if (!cancelled) setState({ kind: "ready", items });
      } catch (e) {
        const msg = (e as Error).message;
        if (!cancelled) {
          if (msg === "AUTH_REQUIRED") setState({ kind: "anonymous" });
          else setState({ kind: "error", msg });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <div className="orders-page">
        <h1>Your orders</h1>
        <p className="empty">Loading…</p>
      </div>
    );
  }

  if (state.kind === "anonymous") {
    return (
      <div className="orders-page">
        <h1>Your orders</h1>
        <p className="empty">Please log in to see your orders.</p>
        <Link href="/login" className="btn btn-primary">
          Log in
        </Link>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="orders-page">
        <p className="error">{state.msg}</p>
      </div>
    );
  }

  return (
    <div className="orders-page">
      <h1>Your orders</h1>
      {state.items.length === 0 ? (
        <>
          <p className="empty">No orders yet.</p>
          <Link href="/search" className="btn btn-primary">
            Browse products
          </Link>
        </>
      ) : (
        <ul className="orders-list">
          {state.items.map((o) => (
            <li key={o.id} className="orders-list__row">
              <Link href={`/orders/${o.id}`} className="orders-list__link">
                <div className="orders-list__id">
                  Order {o.id.slice(0, 8)}…
                </div>
                <div className="orders-list__meta">
                  <span className={`status-badge status-badge--${o.status.toLowerCase()}`}>
                    {o.status.replace("_", " ")}
                  </span>
                  <span className="orders-list__count">
                    {o.seller_order_count} seller{o.seller_order_count === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="orders-list__total">
                  {formatSek(o.total_cents, o.currency)}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
