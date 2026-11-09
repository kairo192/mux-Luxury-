-- See 003_product_variants_updated_at.sqlite.sql for the design rationale.
ALTER TABLE product_variants
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

UPDATE product_variants SET updated_at = COALESCE(created_at, NOW())
 WHERE updated_at IS NULL;

CREATE OR REPLACE FUNCTION trg_variants_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_variants_updated_at ON product_variants;
CREATE TRIGGER trg_variants_updated_at
BEFORE UPDATE ON product_variants
FOR EACH ROW
WHEN (OLD.updated_at IS NOT DISTINCT FROM NEW.updated_at)
EXECUTE FUNCTION trg_variants_set_updated_at();

-- Fresh INSERTs may not supply updated_at from the call site, so stamp them
-- before they're written. The IS NULL guard keeps caller-provided values.
CREATE OR REPLACE FUNCTION trg_variants_set_updated_at_insert()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.updated_at IS NULL THEN
        NEW.updated_at := NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_variants_updated_at_insert ON product_variants;
CREATE TRIGGER trg_variants_updated_at_insert
BEFORE INSERT ON product_variants
FOR EACH ROW
EXECUTE FUNCTION trg_variants_set_updated_at_insert();
