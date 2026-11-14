import { notFound } from "next/navigation";

import ProductCard from "@/components/ProductCard";
import { apiGet } from "@/lib/api";
import type { ProductListItem, StorePage } from "@/lib/types";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export const revalidate = 60;

export default async function StorePageRoute({ params }: PageProps) {
  const { slug } = await params;
  let page: { store: StorePage["store"]; products: ProductListItem[] };
  try {
    page = await apiGet<StorePage>(`/api/v1/shop/stores/${slug}/`);
  } catch {
    notFound();
  }

  return (
    <div className="store-page">
      <header className="store-page__header">
        <h1>{page.store.name}</h1>
        <p className="store-page__owner">
          by {page.store.owner_display_name || "Loomool seller"}
        </p>
        <p className="store-page__count">
          {page.store.product_count} products
        </p>
      </header>

      {page.products.length === 0 ? (
        <p className="empty">This store has no active products yet.</p>
      ) : (
        <div className="product-grid">
          {page.products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
