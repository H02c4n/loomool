import type { Category } from "@/lib/types";
import { productTypeLabel } from "@/lib/format";

const TYPES = [
  "DIY_KIT",
  "MATERIAL",
  "FINISHED_HANDMADE",
  "DIGITAL_PATTERN",
  "WORKSHOP",
  "BUNDLE",
];

export default function SearchFilters({
  categories,
  q,
  category,
  type,
  minPriceCents,
  maxPriceCents,
  inStock,
  sort,
}: {
  categories: Category[];
  q: string;
  category: string;
  type: string;
  minPriceCents: string;
  maxPriceCents: string;
  inStock: boolean;
  sort: string;
}) {
  return (
    <form className="filters" action="/search" method="GET">
      <div className="filters__row">
        <label className="filters__field filters__field--grow">
          <span>Search</span>
          <input
            name="q"
            type="search"
            defaultValue={q}
            placeholder="Search products…"
          />
        </label>
      </div>
      <div className="filters__row">
        <label className="filters__field">
          <span>Category</span>
          <select name="category" defaultValue={category}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="filters__field">
          <span>Type</span>
          <select name="type" defaultValue={type}>
            <option value="">All</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {productTypeLabel(t)}
              </option>
            ))}
          </select>
        </label>
        <label className="filters__field">
          <span>Min (öre)</span>
          <input
            name="min_price_cents"
            type="number"
            min={0}
            defaultValue={minPriceCents}
          />
        </label>
        <label className="filters__field">
          <span>Max (öre)</span>
          <input
            name="max_price_cents"
            type="number"
            min={0}
            defaultValue={maxPriceCents}
          />
        </label>
        <label className="filters__field filters__field--checkbox">
          <input
            name="in_stock"
            type="checkbox"
            value="true"
            defaultChecked={inStock}
          />
          <span>In stock only</span>
        </label>
        <label className="filters__field">
          <span>Sort</span>
          <select name="sort" defaultValue={sort}>
            <option value="">Newest</option>
            <option value="price_asc">Price ↑</option>
            <option value="price_desc">Price ↓</option>
          </select>
        </label>
      </div>
      <div className="filters__actions">
        <button type="submit" className="btn btn-primary">
          Apply
        </button>
      </div>
    </form>
  );
}
