export interface Category {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  children?: Category[];
}

export interface AttributeDefinition {
  id: string;
  key: string;
  label: string;
  type: string;
  required: boolean;
  options: unknown[];
  sort_order: number;
}

export interface CategoryDetail {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  sort_order: number;
  parent: Category | null;
  attribute_definitions: AttributeDefinition[];
  created_at: string;
  updated_at: string;
}

export interface ProductImage {
  id: string;
  url_thumb: string | null;
  url_medium: string | null;
  url_original: string | null;
  width: number;
  height: number;
  alt_text: string;
}

export interface Variant {
  id: string;
  sku: string;
  options: Record<string, unknown>;
  effective_price_cents: number;
  in_stock: boolean;
}

export interface OptionDef {
  key: string;
  label: string;
  values: unknown[];
}

export interface ProductListItem {
  id: string;
  slug: string;
  name: string;
  type: string;
  category_slug: string;
  store_slug: string;
  store_name: string;
  base_price_cents: number;
  currency: string;
  thumb_url: string | null;
}

export interface ProductDetail extends ProductListItem {
  description: string;
  attributes: Record<string, unknown>;
  weight_g: number | null;
  dimensions: Record<string, unknown>;
  images: ProductImage[];
  variants: Variant[];
  option_definitions: OptionDef[];
}

export interface Store {
  id: string;
  slug: string;
  name: string;
  owner_display_name: string;
  product_count: number;
  created_at: string;
}

export interface StorePage {
  store: Store;
  products: ProductListItem[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CartLineProduct {
  id: string;
  slug: string;
  name: string;
  store_slug: string;
  store_name: string;
  thumb_url: string | null;
}

export interface CartLineVariant {
  id: string;
  sku: string;
  options: Record<string, unknown>;
  effective_price_cents: number;
}

export interface CartItem {
  id: string;
  product: CartLineProduct;
  variant: CartLineVariant;
  quantity: number;
  line_total_cents: number;
}

export interface CartGroup {
  store: { id: string; slug: string; name: string };
  items: CartItem[];
  subtotal_cents: number;
}

export interface Cart {
  id: string | null;
  store_groups: CartGroup[];
  total_items: number;
  total_cents: number;
  currency: string;
}

export interface Favorite {
  id: string;
  product: CartLineProduct;
  created_at: string;
}


// ---- Orders --------------------------------------------------------------

export interface OrderListItem {
  id: string;
  status: string;
  total_cents: number;
  currency: string;
  seller_order_count: number;
  expires_at: string;
  created_at: string;
}

export interface OrderItemLine {
  id: string;
  variant: string;
  product_name: string;
  variant_sku: string;
  variant_options: Record<string, unknown>;
  unit_price_cents: number;
  quantity: number;
  line_total_cents: number;
  tax_class: string;
  tax_rate_percent: number;
  commission_rate_percent: number;
  product_slug: string;
  store_slug: string;
  store_name: string;
}

export interface SellerOrder {
  id: string;
  store: string;
  store_slug: string;
  store_name: string;
  status: string;
  subtotal_cents: number;
  currency: string;
  items: OrderItemLine[];
}

export interface OrderDetail {
  id: string;
  status: string;
  total_cents: number;
  currency: string;
  shipping_address: Record<string, unknown>;
  seller_orders: SellerOrder[];
  expires_at: string;
  created_at: string;
  updated_at: string;
  payment_status: string | null;
  can_pay: boolean;
}

export interface CheckoutSession {
  payment_id: string;
  session_id: string;
  checkout_url: string;
}
