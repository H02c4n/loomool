import Link from "next/link";
import { notFound } from "next/navigation";

import AddToCartButton from "@/components/AddToCartButton";
import FavoriteToggle from "@/components/FavoriteToggle";
import {ApiError, apiGet } from "@/lib/api";
import { formatSek, productTypeLabel, rewriteMediaUrl } from "@/lib/format";
import type { ProductDetail } from "@/lib/types";

interface PageProps {
  params: Promise<{ storeSlug: string; productSlug: string }>;
}

export const dynamic = "force-dynamic";

export default async function ProductDetailPage({ params }: PageProps) {
  const { storeSlug, productSlug } = await params;

  let product: ProductDetail;
  try {
    product = await apiGet<ProductDetail>(
      `/api/v1/shop/products/${storeSlug}/${productSlug}/`
    );
  }  catch (err) {
    // Temporary diagnostic — remove once the underlying cause is fixed.
    console.error("[product-detail] fetch failed:", err);
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  const hero = product.images[0];
  const heroUrl = rewriteMediaUrl(hero?.url_medium ?? null);

  return (
    <article className="product-detail">
      <nav className="breadcrumbs">
        <Link href="/search">Shop</Link>
        <span> / </span>
        <Link href={`/stores/${product.store_slug}`}>{product.store_name}</Link>
        <span> / </span>
        <span>{product.name}</span>
      </nav>

      <div className="product-detail__grid">
        <div className="product-detail__gallery">
          {heroUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={heroUrl} alt={hero?.alt_text || product.name} />
          ) : (
            <div className="product-card__placeholder product-detail__placeholder">
              Loomool
            </div>
          )}
        </div>

        <div className="product-detail__info">
          <p className="product-detail__store">
            <Link href={`/stores/${product.store_slug}`}>
              {product.store_name}
            </Link>
          </p>
          <h1>{product.name}</h1>
          <p className="product-detail__type">{productTypeLabel(product.type)}</p>
          <p className="product-detail__price">
            {formatSek(product.base_price_cents, product.currency)}
          </p>

          <div className="product-detail__actions">
            <FavoriteToggle productId={product.id} />
          </div>

          {product.description && (
            <div className="product-detail__description">
              {product.description}
            </div>
          )}

          <div className="product-detail__variants">
            {product.variants.map((v) => (
              <div key={v.id} className="variant-row">
                <div className="variant-row__sku">{v.sku}</div>
                <div className="variant-row__price">
                  {formatSek(v.effective_price_cents, product.currency)}
                </div>
                <div className="variant-row__stock">
                  {v.in_stock ? "In stock" : "Out of stock"}
                </div>
                <AddToCartButton variantId={v.id} disabled={!v.in_stock} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}
