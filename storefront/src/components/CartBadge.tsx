"use client";

import { useEffect, useState } from "react";

import { fetchCart } from "@/lib/api";

export default function CartBadge() {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const cart = await fetchCart();
        if (!cancelled) setCount(cart.total_items);
      } catch {
        if (!cancelled) setCount(0);
      }
    }
    load();
    const onUpdate = () => load();
    window.addEventListener("cart:updated", onUpdate);
    return () => {
      cancelled = true;
      window.removeEventListener("cart:updated", onUpdate);
    };
  }, []);

  if (count === null) return null;
  if (count === 0) return null;
  return <span className="cart-badge__count">{count}</span>;
}
