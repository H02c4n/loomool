"use client";

import { useState } from "react";

import { apiMutate } from "@/lib/api";

export default function AddToCartButton({
  variantId,
  disabled = false,
}: {
  variantId: string;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    try {
      await apiMutate("POST", "/api/v1/shop/cart/items/", {
        variant_id: variantId,
        quantity: 1,
      });
      setAdded(true);
      setTimeout(() => setAdded(false), 2000);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("cart:updated"));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="add-to-cart">
      <button
        type="button"
        className="btn btn-primary"
        onClick={handleClick}
        disabled={busy || disabled || added}
      >
        {added ? "Added ✓" : busy ? "Adding…" : "Add to cart"}
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
