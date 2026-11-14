import Link from "next/link";

import ProductCard from "@/components/ProductCard";
import SearchFilters from "@/components/SearchFilters";
import { apiGet } from "@/lib/api";
import type { Category, Paginated, ProductListItem } from "@/lib/types";

interface SearchPageProps {
  searchParams: Promise<{
    q?: string;
    category?: string;
    type?: string;
    min_price_cents?: string;
    max_price_cents?: string;
    in_stock?: string;
    sort?: string;
    page?: string;
  }>;
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;

  const q = params.q ?? "";
  const category = params.category ?? "";
  const type = params.type ?? "";
  const minPriceCents = params.min_price_cents ?? "";
  const maxPriceCents = params.max_price_cents ?? "";
  const inStock = params.in_stock === "true";
  const sort = params.sort ?? "";
  const page = params.page ?? "1";

  const [results, categories] = await Promise.all([
    apiGet<Paginated<ProductListItem>>("/api/v1/shop/products/", {
      q: q || undefined,
      category: category || undefined,
      type: type || undefined,
      min_price_cents: minPriceCents || undefined,
      max_price_cents: maxPriceCents || undefined,
      in_stock: inStock ? "true" : undefined,
      sort: sort || undefined,
      page,
    }),
    apiGet<Category[]>("/api/v1/catalog/categories/"),
  ]);

  const hasNext = Boolean(results.next);
  const hasPrev = Boolean(results.previous);
  const currentPage = Number(page);
  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(results.count / pageSize));

  function buildPageHref(target: number) {
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    if (category) sp.set("category", category);
    if (type) sp.set("type", type);
    if (minPriceCents) sp.set("min_price_cents", minPriceCents);
    if (maxPriceCents) sp.set("max_price_cents", maxPriceCents);
    if (inStock) sp.set("in_stock", "true");
    if (sort) sp.set("sort", sort);
    sp.set("page", String(target));
    return `/search?${sp.toString()}`;
  }

  return (
    <div className="search-page">
      <h1>Shop</h1>
      <SearchFilters
        categories={categories}
        q={q}
        category={category}
        type={type}
        minPriceCents={minPriceCents}
        maxPriceCents={maxPriceCents}
        inStock={inStock}
        sort={sort}
      />

      <p className="search-page__count">{results.count} results</p>

      {results.results.length === 0 ? (
        <p className="empty">No products matched your filters.</p>
      ) : (
        <div className="product-grid">
          {results.results.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}

      {(hasPrev || hasNext) && (
        <nav className="pagination">
          {hasPrev && (
            <Link href={buildPageHref(currentPage - 1)} className="btn btn-secondary">
              ← Previous
            </Link>
          )}
          <span className="pagination__info">
            Page {currentPage} / {totalPages}
          </span>
          {hasNext && (
            <Link href={buildPageHref(currentPage + 1)} className="btn btn-secondary">
              Next →
            </Link>
          )}
        </nav>
      )}
    </div>
  );
}
