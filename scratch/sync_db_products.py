# scratch/sync_db_products.py
import sqlite3
import json
import re

DB_PATH = "backend/luxe_store.sqlite3"

def seed_products():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT count(*) as cnt FROM products")
    cnt = cur.fetchone()["cnt"]
    print(f"Current products in DB: {cnt}")

    # Build category slug -> id mapping
    cur.execute("SELECT id, slug FROM categories")
    cat_map = {r["slug"]: r["id"] for r in cur.fetchall()}
    print("Categories in DB:", cat_map)

    # Build brand slug -> id mapping
    cur.execute("SELECT id, slug FROM brands")
    brand_map = {r["slug"]: r["id"] for r in cur.fetchall()}
    print("Brands in DB:", brand_map)

    # 11 Products definition
    products_data = [
        {
            "cat_slug": "sacs",
            "brand_slug": "chanel-style",
            "slug": "sac-a-main-chanel-style",
            "sku": "LUX-BAG-001",
            "barcode": "6130001001",
            "name_fr": "Sac à main Chanel style",
            "name_ar": "حقيبة يد ستايل شانيل",
            "name_en": "Chanel Style Quilted Handbag",
            "description_fr": "Un sac iconique au style intemporel. Élégant, pratique et parfait pour toutes les occasions. Ce modèle allie luxe et raffinement avec ses finitions soignées et sa chaîne argentée.",
            "description_ar": "حقيبة أيقونية بتصميم كلاسيكي أنيق ومبطن مع سلسلة معدنية فاخرة.",
            "description_en": "An iconic quilted handbag combining timeless refinement, silver-tone chain strap, and structured luxury.",
            "main_image_url": "/assets/prod_sac_chanel_hd.jpg",
            "purchase_cost": 2600,
            "selling_price": 4500,
            "previous_price": 5500,
            "discount_percent": 18,
            "is_featured": 1,
            "is_new": 1,
            "variants": [
                {"sku": "LUX-BAG-001-BOR-S", "title": "Bordeaux / S", "stock": 3, "price": 4300, "sig": "color:Bordeaux|size:S", "attrs": {"color": "Bordeaux", "size": "S"}},
                {"sku": "LUX-BAG-001-BOR-M", "title": "Bordeaux / M", "stock": 4, "price": 4500, "sig": "color:Bordeaux|size:M", "attrs": {"color": "Bordeaux", "size": "M"}},
                {"sku": "LUX-BAG-001-BOR-L", "title": "Bordeaux / L", "stock": 6, "price": 4500, "sig": "color:Bordeaux|size:L", "attrs": {"color": "Bordeaux", "size": "L"}},
                {"sku": "LUX-BAG-001-NOI-M", "title": "Noir / M", "stock": 5, "price": 4500, "sig": "color:Noir|size:M", "attrs": {"color": "Noir", "size": "M"}},
                {"sku": "LUX-BAG-001-NOI-L", "title": "Noir / L", "stock": 4, "price": 4500, "sig": "color:Noir|size:L", "attrs": {"color": "Noir", "size": "L"}},
                {"sku": "LUX-BAG-001-BEI-M", "title": "Beige / M", "stock": 3, "price": 4500, "sig": "color:Beige|size:M", "attrs": {"color": "Beige", "size": "M"}},
                {"sku": "LUX-BAG-001-ROS-M", "title": "Rose Poudré / M", "stock": 2, "price": 4500, "sig": "color:Rose Poudré|size:M", "attrs": {"color": "Rose Poudré", "size": "M"}},
            ]
        },
        {
            "cat_slug": "chaussures",
            "brand_slug": "mus-luxury",
            "slug": "baskets-elegantes",
            "sku": "LUX-SHOE-001",
            "barcode": "6130002001",
            "name_fr": "Baskets élégantes",
            "name_ar": "حذاء رياضي أنيق",
            "name_en": "Luxury Urban Sneakers",
            "description_fr": "Baskets basses bicolores à semelle confort et finitions dorées subtiles, pensées pour un style urbain chic au quotidien.",
            "description_ar": "حذاء رياضي بتصميم عصري مريح ومناسب للاستخدام اليومي.",
            "description_en": "Contrast black-and-white luxury sneakers crafted for all-day comfort and street elegance.",
            "main_image_url": "/assets/prod_baskets_elegantes.jpg",
            "purchase_cost": 3900,
            "selling_price": 6800,
            "previous_price": 8500,
            "discount_percent": 20,
            "is_featured": 1,
            "is_new": 0,
            "variants": [
                {"sku": "LUX-SHOE-001-BN-37", "title": "Blanc & Noir / 37", "stock": 3, "price": 6800, "sig": "color:Blanc & Noir|size:37", "attrs": {"color": "Blanc & Noir", "size": "37"}},
                {"sku": "LUX-SHOE-001-BN-38", "title": "Blanc & Noir / 38", "stock": 4, "price": 6800, "sig": "color:Blanc & Noir|size:38", "attrs": {"color": "Blanc & Noir", "size": "38"}},
                {"sku": "LUX-SHOE-001-BN-39", "title": "Blanc & Noir / 39", "stock": 6, "price": 6800, "sig": "color:Blanc & Noir|size:39", "attrs": {"color": "Blanc & Noir", "size": "39"}},
                {"sku": "LUX-SHOE-001-BN-40", "title": "Blanc & Noir / 40", "stock": 3, "price": 6800, "sig": "color:Blanc & Noir|size:40", "attrs": {"color": "Blanc & Noir", "size": "40"}},
                {"sku": "LUX-SHOE-001-BN-41", "title": "Blanc & Noir / 41", "stock": 0, "price": 6800, "sig": "color:Blanc & Noir|size:41", "attrs": {"color": "Blanc & Noir", "size": "41"}},
                {"sku": "LUX-SHOE-001-NOI-39", "title": "Noir / 39", "stock": 5, "price": 6800, "sig": "color:Noir|size:39", "attrs": {"color": "Noir", "size": "39"}},
                {"sku": "LUX-SHOE-001-NOI-40", "title": "Noir / 40", "stock": 4, "price": 6800, "sig": "color:Noir|size:40", "attrs": {"color": "Noir", "size": "40"}},
            ]
        },
        {
            "cat_slug": "chale",
            "brand_slug": "maison-or-alger",
            "slug": "echarpe-luxueuse",
            "sku": "LUX-SHW-001",
            "barcode": "6130003001",
            "name_fr": "Écharpe luxueuse",
            "name_ar": "شال فاخر",
            "name_en": "Luxury Printed Shawl",
            "description_fr": "Grand châle doux au toucher soyeux avec motifs ornementaux raffinés. Chaleur, légèreté et élégance.",
            "description_ar": "شال كبير ناعم الملمس بنقوش راقية تمنحك الدفء والأناقة.",
            "description_en": "Large silky shawl featuring delicate gold and caramel ornamental motifs.",
            "main_image_url": "/assets/prod_chale_luxueux.jpg",
            "purchase_cost": 1100,
            "selling_price": 2200,
            "previous_price": 2800,
            "discount_percent": 21,
            "is_featured": 0,
            "is_new": 1,
            "variants": [
                {"sku": "LUX-SHW-001-DOR-180", "title": "Doré Caramel / 180x70cm", "stock": 8, "price": 2200, "sig": "color:Doré Caramel|dimensions:180x70cm", "attrs": {"color": "Doré Caramel", "dimensions": "180x70cm"}},
                {"sku": "LUX-SHW-001-NOI-180", "title": "Noir & Or / 180x70cm", "stock": 6, "price": 2200, "sig": "color:Noir & Or|dimensions:180x70cm", "attrs": {"color": "Noir & Or", "dimensions": "180x70cm"}},
            ]
        },
        {
            "cat_slug": "maquillage",
            "brand_slug": "mus-luxury",
            "slug": "set-maquillage-complet",
            "sku": "LUX-MKP-001",
            "barcode": "6130004001",
            "name_fr": "Set maquillage complet",
            "name_ar": "مجموعة مكياج كاملة",
            "name_en": "Complete Luxury Makeup Set",
            "description_fr": "Coffret beauté réunissant rouges à lèvres satinés, palette ombres à paupières et poudre compacte illuminatrice.",
            "description_ar": "طقم مكياج متكامل يضم أحمر شفاه وباليت ظلال عيون وبودرة مضيئة.",
            "description_en": "Complete beauty set with satin lipsticks, eyeshadow palette, and illuminating compact powder.",
            "main_image_url": "/assets/prod_set_maquillage.jpg",
            "purchase_cost": 2100,
            "selling_price": 3900,
            "previous_price": 5200,
            "discount_percent": 25,
            "is_featured": 1,
            "is_new": 1,
            "variants": [
                {"sku": "LUX-MKP-001-SH01", "title": "Coffret Rose & Nude 01", "stock": 10, "price": 3900, "sig": "shade:Coffret Rose & Nude 01", "attrs": {"shade": "Coffret Rose & Nude 01"}},
                {"sku": "LUX-MKP-001-SH02", "title": "Coffret Rouge & Gold 02", "stock": 7, "price": 3900, "sig": "shade:Coffret Rouge & Gold 02", "attrs": {"shade": "Coffret Rouge & Gold 02"}},
            ]
        },
        {
            "cat_slug": "chapeau",
            "brand_slug": "mus-luxury",
            "slug": "chapeau-elegant",
            "sku": "LUX-HAT-001",
            "barcode": "6130005001",
            "name_fr": "Chapeau élégant",
            "name_ar": "قبعة صيفية أنيقة",
            "name_en": "Summer Fedora Hat",
            "description_fr": "Chapeau de paille tressée haut de gamme avec ruban noir satiné. Allure estivale chic et protection solaire optimale.",
            "description_ar": "قبعة قش فاخرة مع شريط أسود حريري لحماية أنيقة من أشعة الشمس.",
            "description_en": "Braided straw fedora with satin ribbon band for sunny resort days.",
            "main_image_url": "/assets/prod_chapeau_elegant.jpg",
            "purchase_cost": 850,
            "selling_price": 1800,
            "previous_price": 2200,
            "discount_percent": 18,
            "is_featured": 0,
            "is_new": 0,
            "variants": [
                {"sku": "LUX-HAT-001-BEI-M", "title": "Beige Naturel / M (56-57cm)", "stock": 5, "price": 1800, "sig": "color:Beige Naturel|size:M", "attrs": {"color": "Beige Naturel", "size": "M"}},
                {"sku": "LUX-HAT-001-BEI-L", "title": "Beige Naturel / L (58-59cm)", "stock": 4, "price": 1800, "sig": "color:Beige Naturel|size:L", "attrs": {"color": "Beige Naturel", "size": "L"}},
            ]
        },
        {
            "cat_slug": "sacs",
            "brand_slug": "emeraude-paris",
            "slug": "sac-a-main-elegant-emeraude",
            "sku": "LUX-BAG-002",
            "barcode": "6130001002",
            "name_fr": "Sac à main élégant Émeraude",
            "name_ar": "حقيبة يد أسلوب زمردي",
            "name_en": "Emerald Signature Structured Handbag",
            "description_fr": "Sac à main structuré en cuir synthétique haut de gamme vert émeraude avec fermoir et anneaux dorés.",
            "description_ar": "حقيبة يد عصرية فاخرة باللون الأخضر الزمردي مع تفاصيل معدنية ذهبية.",
            "description_en": "Structured emerald handbag with gold-tone accents and refined shoulder strap.",
            "main_image_url": "/assets/prod_sac_emeraude.jpg",
            "purchase_cost": 7200,
            "selling_price": 12500,
            "previous_price": 16900,
            "discount_percent": 26,
            "is_featured": 1,
            "is_new": 1,
            "variants": [
                {"sku": "LUX-BAG-002-EME-STD", "title": "Vert Émeraude / Standard", "stock": 5, "price": 12500, "sig": "color:Vert Émeraude|size:Standard", "attrs": {"color": "Vert Émeraude", "size": "Standard"}},
                {"sku": "LUX-BAG-002-NOI-STD", "title": "Noir Absolu / Standard", "stock": 4, "price": 12500, "sig": "color:Noir Absolu|size:Standard", "attrs": {"color": "Noir Absolu", "size": "Standard"}},
            ]
        },
        {
            "cat_slug": "sacs",
            "brand_slug": "mus-luxury",
            "slug": "sac-bandouliere-beige",
            "sku": "LUX-BAG-003",
            "barcode": "6130001003",
            "name_fr": "Sac bandoulière Beige",
            "name_ar": "حقيبة كتف بيج عصرية",
            "name_en": "Chic Beige Crossbody Bag",
            "description_fr": "Pochette bandoulière moderne couleur crème beige avec bandoulière ajustable et finitions or brossé.",
            "description_ar": "حقيبة كتف بيج أنيقة بحزام قابل للتعديل ومشبك مغناطيسي متين.",
            "description_en": "Chic beige crossbody bag with adjustable strap and brushed gold hardware.",
            "main_image_url": "/assets/prod_sac_bandouliere_beige.jpg",
            "purchase_cost": 5400,
            "selling_price": 9800,
            "previous_price": 11500,
            "discount_percent": 15,
            "is_featured": 1,
            "is_new": 0,
            "variants": [
                {"sku": "LUX-BAG-003-BEI-M", "title": "Crème Beige / Taille Unique", "stock": 7, "price": 9800, "sig": "color:Crème Beige|size:Unique", "attrs": {"color": "Crème Beige", "size": "Unique"}},
            ]
        },
        {
            "cat_slug": "casquette",
            "brand_slug": "mus-luxury",
            "slug": "casquette-brodee-urbaine",
            "sku": "LUX-CAP-001",
            "barcode": "6130006001",
            "name_fr": "Casquette brodée Urbaine",
            "name_ar": "قبعة رياضية مطرزة",
            "name_en": "Embroidered Urban Baseball Cap",
            "description_fr": "Casquette classique en coton lourd 100% avec broderie blanche en relief et boucle métallique arrière.",
            "description_ar": "قبعة كلاسيكية من القطن الممتاز مع تطريز عالي الجودة وحزام قابل للضبط.",
            "description_en": "Classic cotton baseball cap with 3D embroidery and metal adjustment clasp.",
            "main_image_url": "/assets/prod_casquette_ny.jpg",
            "purchase_cost": 1100,
            "selling_price": 2400,
            "previous_price": 3000,
            "discount_percent": 20,
            "is_featured": 0,
            "is_new": 0,
            "variants": [
                {"sku": "LUX-CAP-001-NOI-ADJ", "title": "Noir / Ajustable", "stock": 9, "price": 2400, "sig": "color:Noir|size:Ajustable", "attrs": {"color": "Noir", "size": "Ajustable"}},
                {"sku": "LUX-CAP-001-BLA-ADJ", "title": "Blanc / Ajustable", "stock": 6, "price": 2400, "sig": "color:Blanc|size:Ajustable", "attrs": {"color": "Blanc", "size": "Ajustable"}},
            ]
        },
        {
            "cat_slug": "les-lunettes",
            "brand_slug": "mus-luxury",
            "slug": "lunettes-solaires-prestige",
            "sku": "LUX-SUN-001",
            "barcode": "6130007001",
            "name_fr": "Lunettes solaires Prestige",
            "name_ar": "نظارات شمسية برستيج",
            "name_en": "Prestige Couture Sunglasses",
            "description_fr": "Monture oversize acétate noir intense, verres polarisés catégorie 3 avec protection UV400 intégrale.",
            "description_ar": "نظارات شمسية فاخرة بإطار متين وعدسات مستقطبة تحمي من الأشعة فوق البنفسجية 100%.",
            "description_en": "Oversized black acetate sunglasses with Category 3 polarized UV400 lenses.",
            "main_image_url": "/assets/prod_lunettes_soleil.jpg",
            "purchase_cost": 2800,
            "selling_price": 5400,
            "previous_price": 6800,
            "discount_percent": 21,
            "is_featured": 1,
            "is_new": 1,
            "variants": [
                {"sku": "LUX-SUN-001-NOI-POL", "title": "Noir Brillant / Polarisé", "stock": 8, "price": 5400, "sig": "color:Noir Brillant|lenses:Polarisé", "attrs": {"color": "Noir Brillant", "lenses": "Polarisé"}},
                {"sku": "LUX-SUN-001-ECA-POL", "title": "Écaille Havana / Polarisé", "stock": 4, "price": 5400, "sig": "color:Écaille Havana|lenses:Polarisé", "attrs": {"color": "Écaille Havana", "lenses": "Polarisé"}},
            ]
        },
        {
            "cat_slug": "les-montres",
            "brand_slug": "mus-luxury",
            "slug": "montre-chronographe-imperiale",
            "sku": "LUX-WAT-001",
            "barcode": "6130008001",
            "name_fr": "Montre Chronographe Impériale",
            "name_ar": "ساعة كرونوغراف إمبراطورية",
            "name_en": "Imperial Chronograph Watch",
            "description_fr": "Boîtier acier inoxydable dorure PVD or jaune, cadran noir brossé, chronographe à 3 compteurs et bracelet maillons.",
            "description_ar": "ساعة يد فخمة بطلاء ذهبي ثابت ومينا أسود متألق مع وظيفة الكرونوغراف الدقيقة.",
            "description_en": "Gold PVD stainless steel chronograph with deep black dial and polished link bracelet.",
            "main_image_url": "/assets/prod_montre_or.jpg",
            "purchase_cost": 8900,
            "selling_price": 15900,
            "previous_price": 19500,
            "discount_percent": 18,
            "is_featured": 1,
            "is_new": 1,
            "variants": [
                {"sku": "LUX-WAT-001-OR-41", "title": "Or Jaune & Noir / 41mm", "stock": 4, "price": 15900, "sig": "color:Or Jaune & Noir|dial:41mm", "attrs": {"color": "Or Jaune & Noir", "dial": "41mm"}},
                {"sku": "LUX-WAT-001-ARG-41", "title": "Acier Argenté & Bleu / 41mm", "stock": 3, "price": 15900, "sig": "color:Acier Argenté & Bleu|dial:41mm", "attrs": {"color": "Acier Argenté & Bleu", "dial": "41mm"}},
            ]
        },
        {
            "cat_slug": "accessoires",
            "brand_slug": "maison-or-alger",
            "slug": "parure-bijoux-doree",
            "sku": "LUX-ACC-001",
            "barcode": "6130009001",
            "name_fr": "Parure Bijoux & Bagues Dorées",
            "name_ar": "طقم مجوهرات وخواتم مطلية بالذهب",
            "name_en": "Gilded Jewelry & Rings Set",
            "description_fr": "Ensemble assorti comprenant bague martelée, bracelet jonc délicat et pendentif chaîne dorée haute brillance.",
            "description_ar": "مجموعة مجوهرات أنيقة مطلية بالذهب تشمل خاتماً وسواراً وسلسلة راقية.",
            "description_en": "Matched gold-tone set featuring hammered ring, sleek bangle, and delicate chain pendant.",
            "main_image_url": "/assets/prod_accessoires_or.jpg",
            "purchase_cost": 1900,
            "selling_price": 3800,
            "previous_price": 4900,
            "discount_percent": 22,
            "is_featured": 0,
            "is_new": 1,
            "variants": [
                {"sku": "LUX-ACC-001-DOR-STD", "title": "Doré Éclat / Standard", "stock": 11, "price": 3800, "sig": "color:Doré Éclat|size:Standard", "attrs": {"color": "Doré Éclat", "size": "Standard"}},
            ]
        }
    ]

    inserted_count = 0
    for p in products_data:
        cat_id = cat_map.get(p["cat_slug"])
        brand_id = brand_map.get(p["brand_slug"]) or brand_map.get("mus-luxury")
        if not cat_id:
            print(f"Warning: Category slug {p['cat_slug']} not found in DB! Skipping {p['name_fr']}")
            continue

        # Check if already exists by slug
        cur.execute("SELECT id FROM products WHERE slug = ?", (p["slug"],))
        existing = cur.fetchone()
        if existing:
            print(f"Product {p['slug']} already in DB (id: {existing['id']})")
            continue

        cur.execute(
            """INSERT INTO products
               (category_id, brand_id, slug, sku, barcode, name_fr, name_ar, name_en,
                description_fr, description_ar, description_en, main_image_url,
                purchase_cost_dzd, selling_price_dzd, previous_price_dzd, discount_percent,
                status, is_featured, is_new_arrival)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', ?, ?)""",
            (
                cat_id, brand_id, p["slug"], p["sku"], p["barcode"],
                p["name_fr"], p["name_ar"], p["name_en"],
                p["description_fr"], p["description_ar"], p["description_en"],
                p["main_image_url"],
                p["purchase_cost"], p["selling_price"], p["previous_price"], p["discount_percent"],
                p["is_featured"], p["is_new"]
            )
        )
        prod_id = cur.lastrowid
        inserted_count += 1

        # Insert variants
        for v in p["variants"]:
            cur.execute(
                """INSERT INTO product_variants
                   (product_id, sku, title, stock_qty, price_override_dzd, combination_signature, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (prod_id, v["sku"], v["title"], v["stock"], v["price"], v["sig"], p["main_image_url"])
            )

    conn.commit()
    conn.close()
    print(f"Successfully seeded {inserted_count} new products into database!")

if __name__ == "__main__":
    seed_products()
