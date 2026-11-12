-- Indexes for lookups that read every row without them (PostgreSQL and SQLite).
--
-- Customers screen: total spent / number of orders per customer read orders and
-- POS sales by customer_id. Without an index, every customer scanned all
-- orders: with 20 000 customers and 60 000 orders the screen never loaded
-- (measured: over 2 minutes). Treasury movements are listed newest first.
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_pos_sales_customer_id ON pos_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_cash_movements_created_at ON cash_movements(created_at);
