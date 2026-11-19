"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiBase } from "@/lib/api";
import { rewriteMediaUrl } from "@/lib/format";
import type { Favorite } from "@/lib/types";

type State =
  | { kind: "loading" }
  | { kind: "anonymous" }
  | { kind: "ready"; items: Favorite[] }
  | { kind: "error"; msg: string };

export default function FavoritesPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase()}/api/v1/shop/favorites/`, {
        credentials: "include",
      });
      if (res.status === 401 || res.status === 403) {
        setState({ kind: "anonymous" });
        return;
      }
      if (!res.ok) {
        setState({ kind: "error", msg: `API ${res.status}` });
        return;
      }
      const items = (await res.json()) as Favorite[];
      setState({ kind: "ready", items });
    } catch (e) {
      setState({ kind: "error", msg: (e as Error).message });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (state.kind === "loading") {
    return (
      <div className="favorites-page">
        <p className="empty">Loading…</p>
      </div>
    );
  }

  if (state.kind === "anonymous") {
    return (
      <div className="favorites-page">
        <h1>Your favorites</h1>
        <p className="empty">Log in to see your favorites.</p>
        <Link href="/login" className="btn btn-primary">
          Log in
        </Link>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="favorites-page">
        <p className="error">{state.msg}</p>
      </div>
    );
  }

  return (
    <div className="favorites-page">
      <h1>Your favorites</h1>
      {state.items.length === 0 ? (
        <>
          <p className="empty">No favorites yet.</p>
          <Link href="/search" className="btn btn-primary">
            Browse products
          </Link>
        </>
      ) : (
        <div className="product-grid">
          {state.items.map((fav) => {
            const thumb = rewriteMediaUrl(fav.product.thumb_url);
            return (
              <Link
                key={fav.id}
                href={`/products/${fav.product.store_slug}/${fav.product.slug}`}
                className="product-card"
              >
                <div className="product-card__thumb">
                  {thumb ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={thumb} alt={fav.product.name} />
                  ) : (
                    <span className="product-card__placeholder">kiterpillar</span>
                  )}
                </div>
                <div className="product-card__body">
                  <div className="product-card__store">
                    {fav.product.store_name}
                  </div>
                  <div className="product-card__name">{fav.product.name}</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
