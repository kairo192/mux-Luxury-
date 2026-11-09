-- The POS catalog-deltas endpoint reads product_variants.updated_at as the
-- cursor so the local mirror can ask "what changed since last sync?" without
-- a full re-fetch. The column is additive, so no existing row or code path
-- breaks.
--
-- SQLite refuses `DEFAULT CURRENT_TIMESTAMP` on ADD COLUMN (non-constant
-- default), so we add the column nullable and backfill in the next
-- statement.
ALTER TABLE product_variants ADD COLUMN updated_at TIMESTAMP;

-- Backfill: give every existing row a stable timestamp so the first delta
-- after this migration doesn't pull the entire catalog again. New rows go
-- through the trigger below.
UPDATE product_variants
   SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
 WHERE updated_at IS NULL;

-- Trigger auto-bumps updated_at on every row change, regardless of which
-- call site did the UPDATE. "AFTER UPDATE OF <cols>" narrows the trigger to
-- the columns the mirror cares about and avoids recursion on updated_at
-- itself. On SQLite, recursive triggers are off by default too.
DROP TRIGGER IF EXISTS trg_variants_updated_at;
CREATE TRIGGER trg_variants_updated_at
AFTER UPDATE OF stock_qty, price_override_dzd, title, barcode, sku,
                is_active, image_url, purchase_cost_dzd, low_stock_threshold
ON product_variants
FOR EACH ROW
BEGIN
    UPDATE product_variants SET updated_at = CURRENT_TIMESTAMP
     WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- INSERTs don't run the UPDATE trigger, so brand-new variants would end up
-- with NULL updated_at and be invisible to the mirror's delta cursor. This
-- second trigger stamps new rows at creation time.
DROP TRIGGER IF EXISTS trg_variants_updated_at_insert;
CREATE TRIGGER trg_variants_updated_at_insert
AFTER INSERT ON product_variants
FOR EACH ROW
WHEN NEW.updated_at IS NULL
BEGIN
    UPDATE product_variants SET updated_at = CURRENT_TIMESTAMP
     WHERE id = NEW.id;
END;
