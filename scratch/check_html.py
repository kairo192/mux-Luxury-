with open('apps/storefront/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'<[^>]+id=["\']dynamic-nav-categories["\'][^>]*>', text)
print('HTML element matches for dynamic-nav-categories:', len(matches), matches)

