-- Product characteristics (material, fit, brand…) are optional and typed
-- freely in the CMS. Categories made from the earlier ready-made models had
-- them as REQUIRED drop-down lists of fixed marketing values ("100% Coton
-- Pima Péruvien", brand names…), which blocked or confused the owner.
--   1. no characteristic is required any more;
--   2. those fixed suggestions are removed, except a value a product uses.
-- Runs on PostgreSQL and SQLite.
UPDATE category_attributes SET is_required = 0 WHERE is_required <> 0;

DELETE FROM category_attribute_options
 WHERE value IN (
    'Mus Luxury Signature',
    'Balenciaga',
    'Saint Laurent',
    'Amiri',
    '100% Coton Pima Péruvien',
    'Lin Naturel Aérien',
    'Coton Biologique 280 GSM',
    'Jersey de Soie',
    'Coupe Oversize Couture',
    'Coupe Droite Regular',
    'Coupe Slim / Ajustée',
    'Relaxed Fit',
    'Cuir Nappa Souple',
    'Daim de Veau',
    'Cuir Verni Glacé',
    'Cuir Embossé Croco',
    'Plat (1-2 cm)',
    'Moyen (5-7 cm)',
    'Haut (8-10 cm)',
    'Stiletto (>10 cm)',
    'Sac à main structuré',
    'Pochette du soir',
    'Cabas prestige',
    'Sac bandoulière',
    'Cuir grainé de veau',
    'Cuir lisse pleine fleur',
    'Cuir d''agneau matelassé',
    'Toile monogrammée enduite',
    'Doré poli à l''or fin',
    'Argent Palladié',
    'Ruthénium Brossé',
    'Laiton Vieilli',
    'Acier 316L Poli & Brossé',
    'Or Jaune 18 Carats',
    'Or Rose 18K',
    'Céramique Noire Haute Résistance',
    'Automatique Calibre Manufacture',
    'Chronographe Mécanique Automatique',
    'Quartz Suisse Haute Précision',
    'Alligator Véritable Cousu Main',
    'Acier Maillons Jubilé',
    'Caoutchouc FKM Haute Densité',
    'Mat Poudré Velours',
    'Satin Lumineux',
    'Glossy Vinyle Hydratant',
    'Métallisé Miroir',
    'Verres Polarisés Catégorie 3',
    'Dégradé Brun Protecteur',
    'Miroir Solaire Doré',
    'Verres Photochromiques',
    'Aviateur Iconique',
    'Papillon Cat-Eye',
    'Carré Oversize',
    'Pantos Vintage',
    '100% Soie Naturelle Twill 14mm',
    'Cachemire & Soie Noble',
    'Mousseline de Soie Aérienne',
    'Carré 90 x 90 cm',
    'Grand Carré 140 x 140 cm',
    'Étole 70 x 200 cm',
    '100% Coton Pima',
    'Lin Naturel',
    'Soie Noble'
 )
   AND attribute_id IN (SELECT id FROM category_attributes WHERE is_variant_axis = 0)
   AND NOT EXISTS (
       SELECT 1 FROM product_attribute_values pav
        WHERE pav.attribute_id = category_attribute_options.attribute_id
          AND pav.value_text = category_attribute_options.value
   );
