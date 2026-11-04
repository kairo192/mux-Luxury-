import os
import sys
import json
import time

os.environ["SECRET_KEY"] = "dev_secret_key_mus_luxury_2026_very_secure_long_string_1234567890"
os.environ["CMS_HMAC_SIGNING_SECRET"] = "dev_hmac_signing_secret_mus_luxury_2026_long_key_1234567890"
os.environ["APP_ENV"] = "development"
os.environ["LUXE_DB_ENGINE"] = "sqlite"

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ["LUXE_SQLITE_PATH"] = os.path.join(backend_dir, "luxe_store.sqlite3")
sys.path.insert(0, backend_dir)

from app.database import db_session, init_db

init_db()

with db_session(commit=True) as conn:
    cur = conn.cursor()

    # 1. Coupons
    cur.execute("SELECT COUNT(*) FROM coupons")
    if cur.fetchone()[0] == 0:
        print("Seeding coupons...")
        cur.execute(
            """INSERT INTO coupons (code, discount_type, discount_value, min_order_dzd, max_discount_dzd, is_active)
               VALUES ('BIENVENUE10', 'percentage', 10, 4000, 2500, 1)"""
        )
        cur.execute(
            """INSERT INTO coupons (code, discount_type, discount_value, min_order_dzd, max_discount_dzd, is_active)
               VALUES ('ALGERIE500', 'fixed_dzd', 500, 5000, 500, 1)"""
        )

    # 2. Brands
    cur.execute("SELECT COUNT(*) FROM brands")
    if cur.fetchone()[0] == 0:
        print("Seeding brands...")
        brands = [
            ("Mus Luxury Collection", "mus-luxury", "/assets/mus_luxury_logo.png"),
            ("Chanel Style Privé", "chanel-style", "/assets/mus_luxury_logo.png"),
            ("Émeraude Paris", "emeraude-paris", "/assets/mus_luxury_logo.png"),
            ("Maison Or d'Alger", "maison-or-alger", "/assets/mus_luxury_logo.png"),
        ]
        for bname, bslug, blogo in brands:
            cur.execute("INSERT INTO brands (name, slug, logo_url) VALUES (?, ?, ?)", (bname, bslug, blogo))

    cur.execute("SELECT slug, id FROM brands")
    brand_ids = {r[0]: r[1] for r in cur.fetchall()}

    # 3. Categories
    cur.execute("SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL")
    if cur.fetchone()[0] == 0:
        print("Seeding categories & attributes...")
        initial_categories = [
            ("sacs", "Sacs", "حقائب", "Bags", "Élégance et praticité au quotidien", "/assets/cat_sacs.jpg", 1),
            ("chaussures", "Chaussures", "أحذية", "Shoes", "Baskets et escarpins de haute confection", "/assets/cat_chaussures.jpg", 2),
            ("chale", "Châles", "شالات", "Shawls", "Châles et écharpes en soie et laine fine", "/assets/cat_chale.jpg", 3),
            ("maquillage", "Maquillage", "مكياج", "Makeup", "Cosmétiques et coffrets beauté sélectionnés", "/assets/cat_maquillage.jpg", 4),
            ("chapeau", "Chapeaux", "قبعات كلاسيكية", "Hats", "Chapeaux d'été et feutres raffinés", "/assets/cat_chapeau.jpg", 5),
            ("casquette", "Casquettes", "قبعات رياضية", "Caps", "Casquettes urbaines et sport chic", "/assets/prod_casquette_ny.jpg", 6),
            ("les-lunettes", "Lunettes", "نظارات", "Eyewear", "Lunettes solaires UV400 au style affirmé", "/assets/prod_lunettes_soleil.jpg", 7),
            ("les-montres", "Montres", "ساعات", "Watches", "Garde-temps d'exception et finitions dorées", "/assets/prod_montre_or.jpg", 8),
            ("accessoires", "Accessoires", "إكسسوارات", "Accessories", "Parures, bijoux et petite maroquinerie", "/assets/prod_accessoires_or.jpg", 9),
        ]
        for slug, n_fr, n_ar, n_en, desc_fr, img, order in initial_categories:
            cur.execute(
                """INSERT INTO categories
                   (slug, name_fr, name_ar, name_en, description_fr, image_url, banner_url, display_order, is_active, show_on_homepage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)""",
                (slug, n_fr, n_ar, n_en, desc_fr, img, "/assets/hero_banner_mus.jpg", order)
            )

    cur.execute("SELECT slug, id FROM categories WHERE deleted_at IS NULL")
    cat_ids = {r[0]: r[1] for r in cur.fetchall()}

    def add_attr(cat_slug, key, l_fr, l_ar, l_en, itype, req=0, filt=0, var=0, order=1, unit="", options=None):
        cur.execute("SELECT id FROM category_attributes WHERE category_id = ? AND attr_key = ?", (cat_ids[cat_slug], key))
        row = cur.fetchone()
        if row:
            aid = row[0]
        else:
            cur.execute(
                """INSERT INTO category_attributes
                   (category_id, attr_key, label_fr, label_ar, label_en, input_type, unit, is_required, is_filterable, is_variant_axis, display_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cat_ids[cat_slug], key, l_fr, l_ar, l_en, itype, unit, req, filt, var, order)
            )
            aid = cur.lastrowid
        if options:
            for idx, opt in enumerate(options, start=1):
                val, ol_fr, ol_ar, ol_en, hex_c = opt
                cur.execute("SELECT id FROM category_attribute_options WHERE attribute_id = ? AND value = ?", (aid, val))
                if not cur.fetchone():
                    cur.execute(
                        """INSERT INTO category_attribute_options
                           (attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (aid, val, ol_fr, ol_ar, ol_en, hex_c, idx)
                    )
        return aid

    sacs_color_attr = add_attr("sacs", "color", "Couleur", "اللون", "Color", "color", req=1, filt=1, var=1, order=1, options=[
        ("Bordeaux", "Bordeaux", "خمري", "Burgundy", "#5B1E31"),
        ("Vert Émeraude", "Vert Émeraude", "أخضر زمردي", "Emerald Green", "#063D2E"),
        ("Noir", "Noir", "أسود", "Black", "#181818"),
        ("Beige", "Beige", "بيج", "Beige", "#DFC9AC"),
        ("Rose Poudré", "Rose Poudré", "وردي بودري", "Powder Rose", "#C98594"),
    ])
    sacs_size_attr = add_attr("sacs", "size", "Taille", "المقاس", "Size", "size", req=1, filt=1, var=1, order=2, options=[
        ("Standard", "Standard", "قياسي", "Standard", None),
        ("S", "S", "صغير", "S", None),
        ("M", "M", "متوسط", "M", None),
        ("L", "L", "كبير", "L", None),
    ])
    sacs_type_attr = add_attr("sacs", "bag_type", "Type de sac", "نوع الحقيبة", "Bag Type", "single_select", req=1, filt=1, var=0, order=3, options=[
        ("Sac à main", "Sac à main", "حقيبة يد", "Handbag", None),
        ("Sac bandoulière", "Sac bandoulière", "حقيبة كتف", "Crossbody Bag", None),
        ("Pochette", "Pochette", "محفظة يد", "Clutch", None),
    ])
    sacs_mat_attr = add_attr("sacs", "material", "Matériau", "الخامة", "Material", "short_text", req=1, filt=0, var=0, order=4)
    sacs_dim_attr = add_attr("sacs", "dimensions", "Dimensions", "الأبعاد", "Dimensions", "measurement", req=0, filt=0, var=0, order=5, unit="cm")
    sacs_strap_attr = add_attr("sacs", "strap_type", "Bandoulière", "الحزام", "Strap", "short_text", req=0, filt=0, var=0, order=6)

    cs_color_attr = add_attr("chaussures", "color", "Couleur", "اللون", "Color", "color", req=1, filt=1, var=1, order=1, options=[
        ("Blanc & Noir", "Blanc & Noir", "أبيض وأسود", "White & Black", "#F0F0F0"),
        ("Noir", "Noir", "أسود", "Black", "#1A1A1A"),
        ("Or", "Or", "ذهبي", "Gold", "#D4AF62"),
    ])
    cs_size_attr = add_attr("chaussures", "size", "Pointure", "المقاس", "Size", "size", req=1, filt=1, var=1, order=2, options=[
        ("37", "37", "37", "37", None),
        ("38", "38", "38", "38", None),
        ("39", "39", "39", "39", None),
        ("40", "40", "40", "40", None),
        ("41", "41", "41", "41", None),
    ])

    ch_color_attr = add_attr("chale", "color", "Couleur", "اللون", "Color", "color", req=1, filt=1, var=1, order=1, options=[
        ("Beige & Noir", "Beige & Noir", "بيج وأسود", "Beige & Black", "#DFC9AC"),
        ("Vert Émeraude", "Vert Émeraude", "أخضر زمردي", "Emerald", "#063D2E"),
        ("Or", "Or", "ذهبي", "Gold", "#D4AF62"),
    ])
    ch_dim_attr = add_attr("chale", "dimensions", "Dimensions", "الأبعاد", "Dimensions", "size", req=1, filt=1, var=1, order=2, options=[
        ("180 x 70 cm", "180 x 70 cm", "180 x 70 سم", "180 x 70 cm", None),
        ("200 x 80 cm", "200 x 80 cm", "200 x 80 سم", "200 x 80 cm", None),
    ])

    mq_shade_attr = add_attr("maquillage", "shade", "Teinte / Coffret", "الدرجة", "Shade", "color", req=1, filt=1, var=1, order=1, options=[
        ("Teinte 01 Rose Nude", "Teinte 01 Rose Nude", "درجة 01 وردي نيود", "Shade 01 Rose Nude", "#C98594"),
        ("Teinte 02 Rubis Intense", "Teinte 02 Rubis Intense", "درجة 02 أحمر ياقوتي", "Shade 02 Ruby", "#8B1E2F"),
    ])
    mq_format_attr = add_attr("maquillage", "format", "Format", "الحجم", "Format", "size", req=1, filt=1, var=1, order=2, options=[
        ("Coffret Standard", "Coffret Standard", "مجموعة قياسية", "Standard Set", None),
        ("Coffret Prestige", "Coffret Prestige", "مجموعة بريستيج فاخرة", "Prestige Set", None),
    ])

    # 4. Products & Variants
    cur.execute("SELECT COUNT(*) FROM products WHERE deleted_at IS NULL")
    if cur.fetchone()[0] == 0:
        print("Seeding products & variants...")
        # Product 1
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 1)""",
            (
                cat_ids["sacs"], brand_ids["chanel-style"], "sac-a-main-chanel-style", "LUX-BAG-001", "6130001001",
                "Sac à main Chanel style", "حقيبة يد ستايل شانيل", "Chanel Style Quilted Handbag",
                "Un sac iconique au style intemporel. Élégant, pratique et parfait pour toutes les occasions avec sa chaîne argentée et son cuir matelassé.",
                "حقيبة أيقونية بتصميم كلاسيكي أنيق ومبطن مع سلسلة معدنية فاخرة.",
                "An iconic quilted handbag combining timeless refinement, silver-tone chain strap, and structured luxury.",
                "/assets/prod_sac_chanel_hd.jpg",
                2600, 4500, 5500, 18
            )
        )
        p1_id = cur.lastrowid
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p1_id, sacs_type_attr, "Sac à main"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p1_id, sacs_mat_attr, "Cuir synthétique matelassé premium"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p1_id, sacs_dim_attr, "26 x 15 x 8 cm"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p1_id, sacs_strap_attr, "Chaîne tressée métal & cuir"))

        p1_variants = [
            ("LUX-BAG-001-BOR-L", "Bordeaux / L", 6, "color:Bordeaux|size:L", [("color", sacs_color_attr, "Bordeaux"), ("size", sacs_size_attr, "L")]),
            ("LUX-BAG-001-BOR-M", "Bordeaux / M", 4, "color:Bordeaux|size:M", [("color", sacs_color_attr, "Bordeaux"), ("size", sacs_size_attr, "M")]),
            ("LUX-BAG-001-NOI-L", "Noir / L", 5, "color:Noir|size:L", [("color", sacs_color_attr, "Noir"), ("size", sacs_size_attr, "L")]),
            ("LUX-BAG-001-BEI-M", "Beige / M", 3, "color:Beige|size:M", [("color", sacs_color_attr, "Beige"), ("size", sacs_size_attr, "M")]),
        ]
        for vsku, vtitle, vstock, vsig, vattrs in p1_variants:
            cur.execute(
                "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
                (p1_id, vsku, vtitle, vstock, vsig, "/assets/prod_sac_chanel_hd.jpg")
            )
            vid = cur.lastrowid
            for _, attr_id, val in vattrs:
                cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (vid, attr_id, val))

        # Product 2
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 1)""",
            (
                cat_ids["sacs"], brand_ids["emeraude-paris"], "sac-a-main-elegant-emeraude", "LUX-BAG-002", "6130001002",
                "Sac à main élégant Émeraude", "حقيبة يد أنيقة زمردية", "Emerald Signature Structured Handbag",
                "Sac à main élégant et moderne fabriqué en cuir synthétique haut de gamme avec doublure en tissu doux et fermoir doré.",
                "حقيبة يد عصرية فاخرة باللون الأخضر الزمردي مع شعار ذهبي.",
                "Structured emerald handbag with gold-tone insignia, soft fabric lining, and zip closure.",
                "/assets/prod_sac_emeraude.jpg",
                7200, 12500, 16900, 26
            )
        )
        p2_id = cur.lastrowid
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p2_id, sacs_type_attr, "Sac à main"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p2_id, sacs_mat_attr, "Cuir synthétique haut de gamme"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p2_id, sacs_dim_attr, "28 x 20 x 12 cm"))
        cur.execute(
            "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
            (p2_id, "LUX-BAG-002-EME-STD", "Vert Émeraude / Standard", 5, "color:Vert Émeraude|size:Standard", "/assets/prod_sac_emeraude.jpg")
        )
        v2_id = cur.lastrowid
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v2_id, sacs_color_attr, "Vert Émeraude"))
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v2_id, sacs_size_attr, "Standard"))

        # Product 3
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 0)""",
            (
                cat_ids["sacs"], brand_ids["mus-luxury"], "sac-bandouliere-beige-luxe", "LUX-BAG-003", "6130001003",
                "Sac bandoulière Beige luxe", "حقيبة كتف بيج فاخرة", "Beige Luxe Crossbody Bag",
                "Le compagnon idéal pour vos journées actives. Bandoulière ajustable, finitions soignées et compartiments spacieux.",
                "حقيبة كتف بيج أنيقة وعملية لجميع المناسبات اليومية.",
                "Practical and refined beige crossbody bag with adjustable strap and premium gold zipper accents.",
                "/assets/prod_sac_bandouliere_beige.jpg",
                3800, 6800, 8500, 20
            )
        )
        p3_id = cur.lastrowid
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p3_id, sacs_type_attr, "Sac bandoulière"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p3_id, sacs_mat_attr, "Cuir grainé végan"))
        cur.execute(
            "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
            (p3_id, "LUX-BAG-003-BEI-STD", "Beige / Standard", 7, "color:Beige|size:Standard", "/assets/prod_sac_bandouliere_beige.jpg")
        )
        v3_id = cur.lastrowid
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v3_id, sacs_color_attr, "Beige"))
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v3_id, sacs_size_attr, "Standard"))

        # Product 4 - Shoes
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 1)""",
            (
                cat_ids["chaussures"], brand_ids["mus-luxury"], "baskets-urbaines-elegantes", "LUX-SHO-001", "6130002001",
                "Baskets Urbaines Élégantes", "أحذية رياضية حضرية أنيقة", "Urban Chic Platform Sneakers",
                "Baskets blanches élégantes à semelle épaisse et empiècements contrastés. Confort exceptionnel et look résolument tendance.",
                "حذاء رياضي عصري ومريح بنعل عريض وتفاصيل سوداء وذهبية أنيقة.",
                "Clean-cut luxury platform sneakers offering superior daily cushioning and metallic gold embroidery.",
                "/assets/prod_baskets_elegantes.jpg",
                4200, 7500, 9500, 21
            )
        )
        p4_id = cur.lastrowid
        sho_variants = [
            ("LUX-SHO-001-BN-38", "Blanc & Noir / 38", 5, "color:Blanc & Noir|size:38", [("color", cs_color_attr, "Blanc & Noir"), ("size", cs_size_attr, "38")]),
            ("LUX-SHO-001-BN-39", "Blanc & Noir / 39", 4, "color:Blanc & Noir|size:39", [("color", cs_color_attr, "Blanc & Noir"), ("size", cs_size_attr, "39")]),
            ("LUX-SHO-001-BN-40", "Blanc & Noir / 40", 3, "color:Blanc & Noir|size:40", [("color", cs_color_attr, "Blanc & Noir"), ("size", cs_size_attr, "40")]),
        ]
        for vsku, vtitle, vstock, vsig, vattrs in sho_variants:
            cur.execute(
                "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
                (p4_id, vsku, vtitle, vstock, vsig, "/assets/prod_baskets_elegantes.jpg")
            )
            vid = cur.lastrowid
            for _, attr_id, val in vattrs:
                cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (vid, attr_id, val))

        # Product 5 - Shawl
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 0)""",
            (
                cat_ids["chale"], brand_ids["maison-or-alger"], "chale-soie-cachemire-prestige", "LUX-SHA-001", "6130003001",
                "Châle Soie & Cachemire Prestige", "شال حرير وكشمير بريستيج", "Prestige Silk & Cashmere Shawl",
                "Châle soyeux aux motifs géométriques raffinés. Tissage jacquard doux et chaud, parfait pour sublimer vos tenues d'hiver.",
                "شال فاخر من مزيج الحرير والكشمير بنقوش هندسية دقيقة ودافئة.",
                "Ultra-soft jacquard silk and cashmere shawl with finished fringed borders.",
                "/assets/prod_chale_luxueux.jpg",
                2100, 3900, 4800, 19
            )
        )
        p5_id = cur.lastrowid
        cur.execute(
            "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
            (p5_id, "LUX-SHA-001-BN-STD", "Beige & Noir / 180 x 70 cm", 9, "color:Beige & Noir|dimensions:180 x 70 cm", "/assets/prod_chale_luxueux.jpg")
        )
        v5_id = cur.lastrowid
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v5_id, ch_color_attr, "Beige & Noir"))
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v5_id, ch_dim_attr, "180 x 70 cm"))

        # Product 6 - Makeup
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 1)""",
            (
                cat_ids["maquillage"], brand_ids["mus-luxury"], "coffret-beaute-maquillage-sublime", "LUX-MKP-001", "6130004001",
                "Coffret Beauté & Maquillage Sublime", "مجموعة مكياج وتجميل ساحرة", "Sublime Luxury Makeup Gift Set",
                "Coffret complet comprenant palette d'ombres à paupières veloutées, rouge à lèvres hydratant longue tenue et mascara volume intense.",
                "مجموعة مكياج متكاملة تحتوي على باليت ظلال ناعمة، أحمر شفاه مرطب وماسكارا كثيفة.",
                "Full-face beauty gift set including velvety eyeshadows, long-wear matte lipstick, and high-impact mascara.",
                "/assets/prod_set_maquillage.jpg",
                3200, 5800, 7200, 19
            )
        )
        p6_id = cur.lastrowid
        cur.execute(
            "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
            (p6_id, "LUX-MKP-001-NUDE-STD", "Teinte 01 Rose Nude / Coffret Standard", 8, "shade:Teinte 01 Rose Nude|format:Coffret Standard", "/assets/prod_set_maquillage.jpg")
        )
        v6_id = cur.lastrowid
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v6_id, mq_shade_attr, "Teinte 01 Rose Nude"))
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v6_id, mq_format_attr, "Coffret Standard"))

    # Summary
    cur.execute("SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL")
    cats_final = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products WHERE deleted_at IS NULL")
    prods_final = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM product_variants WHERE is_active = 1")
    vars_final = cur.fetchone()[0]
    print(f"Catalog ready: {cats_final} categories, {prods_final} products, {vars_final} variants in DB!")

