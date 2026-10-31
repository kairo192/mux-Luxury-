import hashlib
import json
from .database import db_session, init_db
from .security import hash_password

SUPPORTED_ATTRIBUTE_TYPES = [
    "short_text", "long_text", "number", "price", "boolean",
    "single_select", "multi_select", "color", "size", "image",
    "date", "measurement", "brand", "barcode_sku"
]

def seed_initial_data() -> None:
    init_db()
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM roles")
        if cur.fetchone()["cnt"] > 0:
            return

        # 1. Roles & Permissions
        cur.execute("INSERT INTO roles (name, description) VALUES (?, ?)", ("super_admin", "Full platform administrator"))
        super_role_id = cur.lastrowid
        cur.execute("INSERT INTO roles (name, description) VALUES (?, ?)", ("catalog_editor", "Catalog & inventory manager without backup/settings access"))
        editor_role_id = cur.lastrowid

        perms = [
            ("dashboard:read", "View dashboard analytics"),
            ("products:write", "Create, edit and delete products & variants"),
            ("categories:write", "Create custom categories and dynamic attributes"),
            ("orders:write", "Manage orders and update statuses"),
            ("content:write", "Manage banners, pages anddelivery zones"),
            ("backups:write", "Trigger and restore backups"),
            ("settings:write", "Manage store settings and users"),
        ]
        for code, desc in perms:
            cur.execute("INSERT INTO permissions (code, description) VALUES (?, ?)", (code, desc))
            pid = cur.lastrowid
            cur.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (super_role_id, pid))
            if code in ("dashboard:read", "products:write", "orders:write"):
                cur.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (editor_role_id, pid))

        # 2. Default Admin Users
        cur.execute(
            "INSERT INTO admin_users (email, full_name, password_hash, role_id, is_active) VALUES (?, ?, ?, ?, 1)",
            ("admin@musluxury.dz", "Mustapha Harbit (Owner)", hash_password("MusLuxury2026!"), super_role_id)
        )
        cur.execute(
            "INSERT INTO admin_users (email, full_name, password_hash, role_id, is_active) VALUES (?, ?, ?, ?, 1)",
            ("editor@musluxury.dz", "Sarah (Catalog Editor)", hash_password("EditorLuxury2026!"), editor_role_id)
        )

        # 3. Store Settings (Brand Identity & Localization)
        settings = {
            "store_name": "Mus Luxury (LUXE)",
            "tagline_fr": "Plus qu'un style, une attitude.",
            "tagline_ar": "أكثر من مجرد أسلوب، إنه موقف.",
            "tagline_en": "More than a style, an attitude.",
            "primary_currency": "DZD",
            "currency_symbol": "DA",
            "default_language": "fr",
            "supported_languages": json.dumps(["fr", "ar", "en"]),
            "colors": json.dumps({
                "deep_emerald": "#063D2E",
                "dark_forest": "#02291F",
                "reflective_gold": "#D4AF62",
                "light_gold": "#E8D4A5",
                "cream_bg": "#F8F6F0",
                "main_text": "#202923",
                "white": "#FFFFFF"
            }),
            "logo_url": "/assets/mus_luxury_logo.png",
            "payment_methods": json.dumps(["cod"]),
            "inventory_policy": "decrement_on_order",
        }
        for k, v in settings.items():
            cur.execute("INSERT INTO store_settings (setting_key, setting_value) VALUES (?, ?)", (k, v))

        # 4. Brands
        brands = [
            ("Mus Luxury Collection", "mus-luxury", "/assets/mus_luxury_logo.png"),
            ("Chanel Style Privé", "chanel-style", "/assets/mus_luxury_logo.png"),
            ("Émeraude Paris", "emeraude-paris", "/assets/mus_luxury_logo.png"),
            ("Maison Or d'Alger", "maison-or-alger", "/assets/mus_luxury_logo.png"),
        ]
        brand_ids = {}
        for bname, bslug, blogo in brands:
            cur.execute("INSERT INTO brands (name, slug, logo_url) VALUES (?, ?, ?)", (bname, bslug, blogo))
            brand_ids[bslug] = cur.lastrowid

        # 5. The 9 Initial Dynamic Categories (Not hardcoded—stored in DB with full dynamic attribute definitions)
        initial_categories = [
            ("sacs", "Sacs", "حقائب", "Bags", "Élégance et praticité au quotidien", "/assets/cat_sacs.jpg", 1),
            ("chaussures", "Chaussures", "أحذية", "Shoes", "Baskets et escarpins de haute confection", "/assets/cat_chaussures.jpg", 2),
            ("chale", "Châle", "شال", "Shawls", "Châles et écharpes en soie et laine fine", "/assets/cat_chale.jpg", 3),
            ("maquillage", "Maquillage", "مكياج", "Makeup", "Cosmétiques et coffrets beauté sélectionnés", "/assets/cat_maquillage.jpg", 4),
            ("chapeau", "Chapeau", "قبعات كلاسيكية", "Hats", "Chapeaux d'été et feutres raffinés", "/assets/cat_chapeau.jpg", 5),
            ("casquette", "Casquette", "قبعات رياضية", "Caps", "Casquettes urbaines et sport chic", "/assets/prod_casquette_ny.jpg", 6),
            ("les-lunettes", "Les lunettes", "نظارات", "Eyewear", "Lunettes solaires UV400 au style affirmé", "/assets/prod_lunettes_soleil.jpg", 7),
            ("les-montres", "Les montres", "ساعات", "Watches", "Garde-temps d'exception et finitions dorées", "/assets/prod_montre_or.jpg", 8),
            ("accessoires", "Accessoires", "إكسسوارات", "Accessories", "Parures, bijoux et petite maroquinerie", "/assets/prod_accessoires_or.jpg", 9),
        ]
        cat_ids = {}
        for slug, n_fr, n_ar, n_en, desc_fr, img, order in initial_categories:
            cur.execute(
                """INSERT INTO categories
                   (slug, name_fr, name_ar, name_en, description_fr, image_url, banner_url, display_order, is_active, show_on_homepage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)""",
                (slug, n_fr, n_ar, n_en, desc_fr, img, "/assets/hero_banner_mus.jpg", order)
            )
            cat_ids[slug] = cur.lastrowid

        # Helper to insert category attributes & options
        def add_attr(cat_slug, key, l_fr, l_ar, l_en, itype, req=0, filt=0, var=0, order=1, unit="", options=None):
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
                    cur.execute(
                        """INSERT INTO category_attribute_options
                           (attribute_id, value, label_fr, label_ar, label_en, color_hex, display_order)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (aid, val, ol_fr, ol_ar, ol_en, hex_c, idx)
                    )
            return aid

        # SACS attributes (Bag type, Color, Size, Material, Dimensions, Strap type)
        sacs_color_attr = add_attr("sacs", "color", "Couleur", "اللون", "Color", "color", req=1, filt=1, var=1, order=1, options=[
            ("Bordeaux", "Bordeaux", "عنابي", "Burgundy", "#5B2333"),
            ("Vert Émeraude", "Vert Émeraude", "أخضر زمردي", "Emerald Green", "#063D2E"),
            ("Noir", "Noir", "أسود", "Black", "#1B1B1B"),
            ("Beige", "Beige", "بيج", "Beige", "#D9C3A9"),
            ("Rose Poudré", "Rose Poudré", "وردي", "Powder Pink", "#C77D8A"),
        ])
        sacs_size_attr = add_attr("sacs", "size", "Taille", "المقاس", "Size", "size", req=1, filt=1, var=1, order=2, options=[
            ("Standard", "Standard", "قياسي", "Standard", None),
            ("S", "Petit (S)", "صغير", "Small", None),
            ("M", "Moyen (M)", "متوسط", "Medium", None),
            ("L", "Grand (L)", "كبير", "Large", None),
        ])
        sacs_type_attr = add_attr("sacs", "bag_type", "Type de sac", "نوع الحقيبة", "Bag Type", "single_select", req=1, filt=1, var=0, order=3, options=[
            ("Sac à main", "Sac à main", "حقيبة يد", "Handbag", None),
            ("Sac bandoulière", "Sac bandoulière", "حقيبة كتف", "Crossbody Bag", None),
            ("Sac de voyage", "Sac de voyage", "حقيبة سفر", "Travel Bag", None),
        ])
        sacs_mat_attr = add_attr("sacs", "material", "Matériau", "الخامة", "Material", "short_text", req=1, filt=0, var=0, order=4)
        sacs_dim_attr = add_attr("sacs", "dimensions", "Dimensions", "الأبعاد", "Dimensions", "measurement", req=0, filt=0, var=0, order=5, unit="cm")
        sacs_strap_attr = add_attr("sacs", "strap_type", "Type de bandoulière", "نوع الحزام", "Strap Type", "short_text", req=0, filt=0, var=0, order=6)

        # CHAUSSURES attributes (Gender, Color, Size, Material, Shoe Type, Season)
        ch_color_attr = add_attr("chaussures", "color", "Couleur", "اللون", "Color", "color", req=1, filt=1, var=1, order=1, options=[
            ("Blanc & Noir", "Blanc & Noir", "أبيض وأسود", "White & Black", "#F5F5F5"),
            ("Noir", "Noir", "أسود", "Black", "#1B1B1B"),
            ("Or", "Or", "ذهبي", "Gold", "#D4AF62"),
        ])
        ch_size_attr = add_attr("chaussures", "size", "Pointure", "المقاس", "Shoe Size", "size", req=1, filt=1, var=1, order=2, options=[
            ("37", "37", "37", "37", None),
            ("38", "38", "38", "38", None),
            ("39", "39", "39", "39", None),
            ("40", "40", "40", "40", None),
            ("41", "41", "41", "41", None),
        ])
        ch_gender_attr = add_attr("chaussures", "gender", "Genre", "الجنس", "Gender", "single_select", req=1, filt=1, var=0, order=3, options=[
            ("Femme", "Femme", "نساء", "Women", None),
            ("Homme", "Homme", "رجال", "Men", None),
            ("Unisexe", "Unisexe", "للجنسين", "Unisex", None),
        ])
        ch_mat_attr = add_attr("chaussures", "material", "Matériau", "الخامة", "Material", "short_text", req=1, filt=0, var=0, order=4)
        ch_type_attr = add_attr("chaussures", "shoe_type", "Type de chaussure", "نوع الحذاء", "Shoe Type", "single_select", req=1, filt=1, var=0, order=5, options=[
            ("Baskets", "Baskets", "حذاء رياضي", "Sneakers", None),
            ("Escarpins", "Escarpins", "كعب عالي", "Heels", None),
            ("Mocassins", "Mocassins", "موكاسين", "Loafers", None),
        ])

        # MAQUILLAGE attributes (Shade, Skin Type, Finish, Volume/Weight, Ingredients, Expiration Date)
        mq_shade_attr = add_attr("maquillage", "shade", "Teinte / Coffret", "الدرجة", "Shade", "color", req=1, filt=1, var=1, order=1, options=[
            ("Coffret Rose & Nude 01", "Coffret Rose & Nude 01", "مجموعة روز ونود 01", "Rose & Nude Set 01", "#B6465F"),
            ("Coffret Rubis & Or 02", "Coffret Rubis & Or 02", "مجموعة روبي وذهبي 02", "Ruby & Gold Set 02", "#8E1B2B"),
        ])
        mq_skin_attr = add_attr("maquillage", "skin_type", "Type de peau", "نوع البشرة", "Skin Type", "single_select", req=1, filt=1, var=0, order=2, options=[
            ("Tous types de peau", "Tous types de peau", "جميع أنواع البشرة", "All Skin Types", None),
            ("Peau sensible", "Peau sensible", "بشرة حساسة", "Sensitive Skin", None),
        ])
        mq_finish_attr = add_attr("maquillage", "finish", "Fini", "اللمسة النهائية", "Finish", "single_select", req=1, filt=1, var=0, order=3, options=[
            ("Satiné & Velours", "Satiné & Velours", "ساتان ومخملي", "Satin & Velvet", None),
            ("Mat", "Mat", "مات", "Matte", None),
        ])
        mq_vol_attr = add_attr("maquillage", "volume", "Volume / Poids", "الحجم / الوزن", "Volume / Weight", "measurement", req=1, filt=0, var=0, order=4, unit="g")

        # MONTRES attributes (Movement, Case Material, Strap Material, Dial Color, Water Resistance)
        mt_dial_attr = add_attr("les-montres", "dial_color", "Couleur du cadran", "لون الميناء", "Dial Color", "color", req=1, filt=1, var=1, order=1, options=[
            ("Noir & Or", "Noir & Or", "أسود وذهبي", "Black & Gold", "#1A2421"),
            ("Vert Émeraude & Or", "Vert Émeraude & Or", "أخضر زمردي وذهبي", "Emerald & Gold", "#063D2E"),
        ])
        mt_mov_attr = add_attr("les-montres", "movement", "Mouvement", "حركة الساعة", "Movement", "single_select", req=1, filt=1, var=0, order=2, options=[
            ("Chronographe Quartz Précision", "Chronographe Quartz Précision", "كرونوغراف كوارتز", "Precision Quartz Chronograph", None),
            ("Automatique", "Automatique", "أوتوماتيك", "Automatic", None),
        ])
        mt_water_attr = add_attr("les-montres", "water_resistance", "Étanchéité", "مقاومة الماء", "Water Resistance", "short_text", req=1, filt=0, var=0, order=3)

        # LUNETTES attributes
        ln_frame_attr = add_attr("les-lunettes", "frame_color", "Couleur de monture", "لون الإطار", "Frame Color", "color", req=1, filt=1, var=1, order=1, options=[
            ("Écaille & Or", "Écaille & Or", "بني مذهب", "Tortoise & Gold", "#4A2E1B"),
            ("Noir Intense", "Noir Intense", "أسود داكن", "Deep Black", "#141414"),
        ])
        ln_uv_attr = add_attr("les-lunettes", "uv_protection", "Protection UV", "حماية الأشعة", "UV Protection", "short_text", req=1, filt=1, var=0, order=2)

        # 6. Seed Algerian Wilayas & Delivery Rates
        wilayas = [
            ("16", "Alger", "الجزائر", ["Alger Centre", "Hydra", "Bab Ezzouar", "Chéraga", "Dély Ibrahim", "Kouba"], 400, 300, "24h"),
            ("31", "Oran", "وهران", ["Oran Centre", "Bir El Djir", "Es Senia", "Arzew"], 600, 400, "24h - 48h"),
            ("25", "Constantine", "قسنطينة", ["Constantine", "El Khroub", "Ali Mendjeli", "Hamma Bouziane"], 600, 400, "24h - 48h"),
            ("19", "Sétif", "سطيف", ["Sétif", "El Eulma", "Aïn Oulmene"], 600, 400, "24h - 48h"),
            ("09", "Blida", "البليدة", ["Blida", "Boufarik", "Ouled Yaïch"], 500, 350, "24h"),
            ("06", "Béjaïa", "بجاية", ["Béjaïa", "Akbou", "El Kseur"], 650, 450, "48h"),
            ("15", "Tizi Ouzou", "تيزي وزو", ["Tizi Ouzou", "Azazga", "Draâ Ben Khedda"], 600, 400, "24h - 48h"),
            ("23", "Annaba", "عنابة", ["Annaba", "El Bouni", "Sidi Amar"], 650, 450, "48h"),
            ("13", "Tlemcen", "تلمسان", ["Tlemcen", "Maghnia", "Mansourah"], 700, 450, "48h"),
            ("30", "Ouargla", "ورقلة", ["Ouargla", "Hassi Messaoud", "Touggourt"], 900, 600, "48h - 72h"),
        ]
        for code, w_fr, w_ar, communes, home_fee, desk_fee, est in wilayas:
            cur.execute(
                "INSERT INTO delivery_zones (wilaya_code, wilaya_name_fr, wilaya_name_ar, communes_json, is_active) VALUES (?, ?, ?, ?, 1)",
                (code, w_fr, w_ar, json.dumps(communes, ensure_ascii=False))
            )
            zid = cur.lastrowid
            cur.execute(
                "INSERT INTO delivery_rates (zone_id, delivery_method, fee_dzd, estimated_days, is_supported) VALUES (?, 'home', ?, ?, 1)",
                (zid, home_fee, est)
            )
            cur.execute(
                "INSERT INTO delivery_rates (zone_id, delivery_method, fee_dzd, estimated_days, is_supported) VALUES (?, 'stop_desk', ?, ?, 1)",
                (zid, desk_fee, est)
            )

        # 7. Seed Authentic Initial Catalog Products & Variants matching the Owner's Mockups
        # Product 1: Sac à main Chanel style (4 500 DA, prev 5 500 DA)
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

        # Product 2: Sac à main élégant Émeraude (12 500 DA, prev 16 900 DA)
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

        # Product 3: Baskets élégantes (6 800 DA, prev 8 500 DA)
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 0)""",
            (
                cat_ids["chaussures"], brand_ids["mus-luxury"], "baskets-elegantes-urbaines", "LUX-SHOE-001", "6130002001",
                "Baskets élégantes", "حذاء رياضي أنيق", "Luxury Urban Sneakers",
                "Baskets basses au design contrasté noir et blanc avec finitions dorées subtiles et semelle confort.",
                "حذاء رياضي بتصميم عصري مريح ومناسب للاستخدام اليومي.",
                "Contrast black-and-white luxury sneakers crafted for all-day comfort and street elegance.",
                "/assets/prod_baskets_elegantes.jpg",
                3900, 6800, 8500, 20
            )
        )
        p3_id = cur.lastrowid
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p3_id, ch_gender_attr, "Unisexe"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p3_id, ch_mat_attr, "Cuir grainé & semelle caoutchouc"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p3_id, ch_type_attr, "Baskets"))

        for sz, stk in [("38", 4), ("39", 6), ("40", 3), ("41", 0)]:
            cur.execute(
                "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
                (p3_id, f"LUX-SHOE-001-BN-{sz}", f"Blanc & Noir / {sz}", stk, f"color:Blanc & Noir|size:{sz}", "/assets/prod_baskets_elegantes.jpg")
            )
            vid = cur.lastrowid
            cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (vid, ch_color_attr, "Blanc & Noir"))
            cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (vid, ch_size_attr, sz))

        # Product 4: Set maquillage complet (3 900 DA, prev 5 200 DA)
        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1, 1)""",
            (
                cat_ids["maquillage"], brand_ids["mus-luxury"], "set-maquillage-complet", "LUX-MKP-001", "6130004001",
                "Set maquillage complet", "مجموعة مكياج كاملة", "Complete Luxury Makeup Set",
                "Coffret beauté réunissant rouges à lèvres satinés, palette ombres à paupières et poudre compacte illuminatrice.",
                "طقم مكياج متكامل يضم أحمر شفاه وباليت ظلال عيون وبودرة مضيئة.",
                "Complete beauty set with satin lipsticks, eyeshadow palette, and illuminating compact powder.",
                "/assets/prod_set_maquillage.jpg",
                2100, 3900, 5200, 25
            )
        )
        p4_id = cur.lastrowid
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p4_id, mq_skin_attr, "Tous types de peau"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p4_id, mq_finish_attr, "Satiné & Velours"))
        cur.execute("INSERT INTO product_attribute_values (product_id, attribute_id, value_text) VALUES (?, ?, ?)", (p4_id, mq_vol_attr, "145 g"))
        cur.execute(
            "INSERT INTO product_variants (product_id, sku, title, stock_qty, combination_signature, image_url) VALUES (?, ?, ?, ?, ?, ?)",
            (p4_id, "LUX-MKP-001-SH01", "Coffret Rose & Nude 01", 10, "shade:Coffret Rose & Nude 01", "/assets/prod_set_maquillage.jpg")
        )
        v4_id = cur.lastrowid
        cur.execute("INSERT INTO variant_attribute_values (variant_id, attribute_id, option_value) VALUES (?, ?, ?)", (v4_id, mq_shade_attr, "Coffret Rose & Nude 01"))

        # 8. Seed Initial Backup Record
        cur.execute(
            "INSERT INTO backup_records (filename, backup_type, size_bytes, sha256_checksum, status, triggered_by) VALUES (?, 'full', 248920, ?, 'verified', 1)",
            ("luxe_backup_initial_20261031.sql.gz", hashlib.sha256(b"initial_luxe_seed").hexdigest())
        )


        # 9. Seed Homepage Sections & Promotional Banners (Controlled by Tauri 2 Desktop CMS)
        sections = [
            ("hero_banner", "Bannière Principale Hero", "البانر الرئيسي", "Main Hero Banner", 1, 1, json.dumps({
                "badge_fr": "STYLE • QUALITÉ • ÉLÉGANCE",
                "title_line1_fr": "Votre style,",
                "title_line2_fr": "notre passion",
                "description_fr": "Découvrez notre sélection exclusive de sacs, chaussures, châles, maquillage, montres et accessoires aux finitions irréprochables.",
                "cta_primary_fr": "Découvrir la collection"
            }, ensure_ascii=False)),
            ("trust_bar", "Barre de Confiance (4 Garanties)", "شريط الثقة", "Trust Indicators Bar", 1, 2, "{}"),
            ("categories_grid", "Grille Nos Catégories", "شبكة الفئات", "Shop by Category Grid", 1, 3, "{}"),
            ("featured_products", "Produits en Vedette & Catalogue", "المنتجات المميزة", "Featured Products", 1, 4, "{}"),
            ("promo_banners", "Bannières Promotionnelles Saisonnières", "العروض الموسمية", "Seasonal Promo Banners", 1, 5, "{}"),
        ]
        for skey, t_fr, t_ar, t_en, is_act, d_ord, cfg in sections:
            cur.execute(
                "INSERT INTO homepage_sections (section_key, title_fr, title_ar, title_en, is_active, display_order, config_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (skey, t_fr, t_ar, t_en, is_act, d_ord, cfg)
            )

        banners = [
            ("hero", "Votre style, notre passion", "أسلوبك، شغفنا الدائم", "Your style, our passion",
             "Découvrez les meilleures marques et les plus beaux accessoires en Algérie.",
             "Voir la boutique", "/categories/sacs", "/assets/hero_banner_mus.jpg", 1, 1),
            ("promo_grid", "CHAUSSURES — Jusqu'à -20%", "أحذية — تخفيض حتى 20%", "SHOES — Up to 20% Off",
             "Baskets & créations urbaines", "Voir la collection", "/categories/chaussures", "/assets/prod_baskets_elegantes.jpg", 1, 2),
            ("promo_grid", "LUNETTES — Élégance & UV400", "نظارات — أناقة وحماية", "EYEWEAR — UV400 Elegance",
             "Montures écaille et dorées", "Voir la collection", "/categories/les-lunettes", "/assets/prod_lunettes_soleil.jpg", 1, 3),
            ("promo_grid", "MONTRES — Le temps du style", "ساعات — وقت الأناقة", "WATCHES — Time for Style",
             "Chronographes acier & or", "Voir la collection", "/categories/les-montres", "/assets/prod_montre_or.jpg", 1, 4),
        ]
        for pos, tf, ta, te, subf, cta, link, img, act, ord_i in banners:
            cur.execute(
                """INSERT INTO banners
                   (position, title_fr, title_ar, title_en, subtitle_fr, cta_text_fr, cta_link, image_url, is_active, display_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pos, tf, ta, te, subf, cta, link, img, act, ord_i)
            )
