import Link from "next/link";

import { formatSek, rewriteMediaUrl } from "@/lib/format";
import type { ProductListItem } from "@/lib/types";

export default function ProductCard({ product }: { product: ProductListItem }) {
  const thumb = rewriteMediaUrl(product.thumb_url);
  return (
    <Link
      href={`/products/${product.store_slug}/${product.slug}`}
      className="product-card"
    >
      <div className="product-card__thumb">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={product.name} />
        ) : (
          <span className="product-card__placeholder">Loomool</span>
        )}
      </div>
      <div className="product-card__body">
        <div className="product-card__store">{product.store_name}</div>
        <div className="product-card__name">{product.name}</div>
        <div className="product-card__price">
          {formatSek(product.base_price_cents, product.currency)}
        </div>
      </div>
    </Link>
  );
}
