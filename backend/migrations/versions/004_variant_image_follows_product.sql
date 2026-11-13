-- A variant's image_url now means "this variant has ITS OWN photo" (e.g. the
-- red version of a bag). NULL means "use the product's main photo".
--
-- Until now every variant was created with a COPY of the product's main
-- photo, so after the owner changed the main photo the shop still showed the
-- old one whenever a customer picked a colour/size. Clear the copies that are
-- identical to the current main photo; variants with a different (deliberate)
-- photo are left untouched. Runs on PostgreSQL and SQLite.
UPDATE product_variants
   SET image_url = NULL
 WHERE image_url IS NOT NULL
   AND image_url = (SELECT p.main_image_url FROM products p WHERE p.id = product_variants.product_id);
