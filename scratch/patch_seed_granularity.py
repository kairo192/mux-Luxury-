import re

path = 'backend/app/seed.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any hero_banner_mus.jpg with hero_bag_clean.jpg
content = content.replace('/assets/hero_banner_mus.jpg', '/assets/hero_bag_clean.jpg')

# Replace the single early-return guard:
old_guard = '''    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM roles")
        if cur.fetchone()["cnt"] > 0:
            return'''

new_guard = '''    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM roles")
        roles_already_seeded = cur.fetchone()["cnt"] > 0'''

if old_guard in content:
    content = content.replace(old_guard, new_guard)
    # Wrap section 1 & 2 in `if not roles_already_seeded:`
    content = content.replace(
        '        # 1. All 6 Required RBAC Roles (Section 7 of Master Prompt)',
        '        if not roles_already_seeded:\n            # 1. All 6 Required RBAC Roles (Section 7 of Master Prompt)'
    )
    # The end of section 2 is before `# 3. Official Mus Luxury Store Settings`
    content = content.replace(
        '        # 3. Official Mus Luxury Store Settings (Section 4.10)',
        '        # 3. Official Mus Luxury Store Settings (Section 4.10)\n        cur.execute("SELECT COUNT(*) AS cnt FROM store_settings")\n        if cur.fetchone()["cnt"] == 0:'
    )
    # Now check brands
    content = content.replace(
        '        # 5. Brands',
        '        cur.execute("SELECT COUNT(*) AS cnt FROM brands")\n        if cur.fetchone()["cnt"] == 0:\n            brands_to_seed = True\n        else:\n            brands_to_seed = False\n        # 5. Brands'
    )

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated backend/app/seed.py successfully.")
