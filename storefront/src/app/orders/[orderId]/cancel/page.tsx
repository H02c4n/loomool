"use client";

import Link from "next/link";
import { use } from "react";

export default function CancelPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const { orderId } = use(params);

  return (
    <div className="payment-result">
      <h1>Payment cancelled</h1>
      <p>Your order is still awaiting payment. Stock is held until the order expires.</p>
      <div className="payment-result__actions">
        <Link href={`/orders/${orderId}`} className="btn btn-primary">
          Try again
        </Link>
        <Link href="/orders" className="btn btn-secondary">
          My orders
        </Link>
      </div>
    </div>
  );
}
