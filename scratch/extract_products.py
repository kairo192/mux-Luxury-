# scratch/extract_products.py
with open("apps/storefront/index.html", "r", encoding="utf-8") as f:
    text = f.read()

import re

# Find PRODUCTS = [ ... ]
p_start = text.find("const PRODUCTS = [")
p_end = text.find("];", p_start)
if p_start != -1 and p_end != -1:
    chunk = text[p_start:p_end+2]
    # Find all name_fr
    names = re.findall(r'name_fr:\s*"([^"]+)"', chunk)
    skus = re.findall(r'sku:\s*"([^"]+)"', chunk)
    slugs = re.findall(r'category_slug:\s*"([^"]+)"', chunk)
    prices = re.findall(r'selling_price_dzd:\s*(\d+)', chunk)
    print(f"Found {len(names)} products:")
    for i in range(len(names)):
        print(f"{i+1}. {names[i]} | SKU: {skus[i] if i < len(skus) else 'N/A'} | Cat: {slugs[i] if i < len(slugs) else 'N/A'} | Price: {prices[i] if i < len(prices) else 'N/A'} DA")
