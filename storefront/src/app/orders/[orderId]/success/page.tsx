"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { fetchOrder } from "@/lib/api";
import type { OrderDetail } from "@/lib/types";

type State =
  | { kind: "polling" }
  | { kind: "paid"; order: OrderDetail }
  | { kind: "timeout" }
  | { kind: "error"; msg: string };

export default function SuccessPage({
  params,
  searchParams,
}: {
  params: Promise<{ orderId: string }>;
  searchParams: Promise<{ session_id?: string }>;
}) {
  const { orderId } = use(params);
  // Consume searchParams to satisfy the type contract; the value is informational.
  use(searchParams);

  const [state, setState] = useState<State>({ kind: "polling" });

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 24; // 24 × 2.5s = 60s

    const tick = async () => {
      try {
        const order = await fetchOrder(orderId);
        if (cancelled) return;
        if (order.status === "PAID") {
          setState({ kind: "paid", order });
          return;
        }
        attempts += 1;
        if (attempts >= maxAttempts) {
          setState({ kind: "timeout" });
          return;
        }
        setTimeout(tick, 2500);
      } catch (e) {
        if (!cancelled) setState({ kind: "error", msg: (e as Error).message });
      }
    };

    tick();
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  if (state.kind === "polling") {
    return (
      <div className="payment-result">
        <h1>Processing your payment…</h1>
        <p className="empty">This page will refresh automatically.</p>
      </div>
    );
  }

  if (state.kind === "timeout") {
    return (
      <div className="payment-result">
        <h1>Payment is taking longer than expected</h1>
        <p>
          If you completed the payment, it will be processed shortly. Check
          your order or contact support if the status does not update.
        </p>
        <Link href={`/orders/${orderId}`} className="btn btn-primary">
          View order
        </Link>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="payment-result">
        <p className="error">{state.msg}</p>
        <Link href={`/orders/${orderId}`} className="btn btn-secondary">
          Back to order
        </Link>
      </div>
    );
  }

  return (
    <div className="payment-result">
      <h1>Payment received</h1>
      <p>Thank you! Your order has been confirmed.</p>
      <Link href={`/orders/${orderId}`} className="btn btn-primary">
        View order
      </Link>
    </div>
  );
}
