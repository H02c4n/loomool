"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiBase, apiMutate } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "anonymous" }
  | { kind: "ready"; favorited: boolean }
  | { kind: "error" };

export default function FavoriteToggle({ productId }: { productId: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase()}/api/v1/shop/favorites/`, {
        credentials: "include",
      });
      if (res.status === 401 || res.status === 403) {
        setState({ kind: "anonymous" });
        return;
      }
      if (!res.ok) {
        setState({ kind: "error" });
        return;
      }
      const data = (await res.json()) as { product: { id: string } }[];
      setState({
        kind: "ready",
        favorited: data.some((f) => f.product.id === productId),
      });
    } catch {
      setState({ kind: "error" });
    }
  }, [productId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function toggle() {
    setBusy(true);
    try {
      const res = await apiMutate<unknown>(
        "POST",
        "/api/v1/shop/favorites/toggle/",
        { product_id: productId }
      );
      // 201 with body = now favorited; 204 = null = removed.
      setState({ kind: "ready", favorited: res !== null });
    } catch {
      // keep current state on error
    } finally {
      setBusy(false);
    }
  }

  if (state.kind === "loading" || state.kind === "error") return null;
  if (state.kind === "anonymous") {
    return (
      <Link href="/login" className="btn-favorite btn-favorite--anon">
        ♡ Log in to save
      </Link>
    );
  }

  return (
    <button
      type="button"
      className={`btn-favorite ${state.favorited ? "is-active" : ""}`}
      onClick={toggle}
      disabled={busy}
      aria-label={state.favorited ? "Remove from favorites" : "Add to favorites"}
    >
      {state.favorited ? "♥ Saved" : "♡ Save"}
    </button>
  );
}
