import Link from "next/link";

import ProductCard from "@/components/ProductCard";
import { apiGet } from "@/lib/api";
import type { Category, Paginated, ProductListItem } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [products, categories] = await Promise.all([
    apiGet<Paginated<ProductListItem>>("/api/v1/shop/products/", {
      page_size: 8,
    }),
    apiGet<Category[]>("/api/v1/catalog/categories/"),
  ]);

  return (
    <>
      <section className="hero">
        <h1>Make it. Kit it. Sell it.</h1>
        <p>
          Discover handmade goods, ready-to-craft kits and creative workshops —
          from independent makers across Sweden.
        </p>
        <Link href="/search" className="btn btn-primary">
          Browse all products
        </Link>
      </section>

      {categories.length > 0 && (
        <section className="section">
          <h2>Browse by category</h2>
          <div className="category-grid">
            {categories.map((c) => (
              <Link
                key={c.id}
                href={`/search?category=${c.slug}`}
                className="category-tile"
              >
                {c.name}
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <h2>Latest arrivals</h2>
        {products.results.length === 0 ? (
          <p className="empty">No products yet.</p>
        ) : (
          <div className="product-grid">
            {products.results.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
