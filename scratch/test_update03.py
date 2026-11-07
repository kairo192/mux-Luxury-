# test_update03.py
import re

print("Starting test update 03 preparation...")
with open("apps/storefront/index.html", "r", encoding="utf-8") as f:
    content = f.read()

print(f"Original content length: {len(content)} characters")

