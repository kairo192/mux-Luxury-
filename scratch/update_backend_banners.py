with open('backend/app/main.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('banner_url: Optional[str] = "/assets/hero_banner_mus.jpg"', 'banner_url: Optional[str] = "/assets/hero_bag_clean.jpg"')
c = c.replace('image_url: str = "/assets/hero_banner_mus.jpg"', 'image_url: str = "/assets/hero_bag_clean.jpg"')
with open('backend/app/main.py', 'w', encoding='utf-8') as f:
    f.write(c)

with open('backend/app/seed.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('/assets/hero_banner_mus.jpg', '/assets/hero_bag_clean.jpg')
with open('backend/app/seed.py', 'w', encoding='utf-8') as f:
    f.write(c)

with open('backend/scripts/run_seed_sections.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('/assets/hero_banner_mus.jpg', '/assets/hero_bag_clean.jpg')
with open('backend/scripts/run_seed_sections.py', 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated banner defaults in backend successfully.')
