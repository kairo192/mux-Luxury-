// Data shapes used by the till (Caisse).

export interface RegisterSession {
  id: number;
  register_name: string;
  opening_float_dzd: number;
  expected_cash_dzd?: number;
  sales_total_dzd?: number;
  refunds_total_dzd?: number;
  sales_count?: number;
  opened_at: string;
  status: string;
}

export interface LookupVariant {
  variant_id: number;
  product_id: number;
  product_name: string;
  variant_title: string;
  sku: string;
  barcode?: string | null;
  unit_price_dzd: number;
  stock_qty: number;
  main_image_url?: string | null;
}

export interface CartLine {
  variant_id: number;
  product_id: number;
  product_name: string;
  variant_title: string;
  sku: string;
  unit_price_dzd: number;
  quantity: number;
  line_discount_dzd: number;
  stock_qty: number;
}

export type PaymentMethod = "cash" | "card" | "transfer";
