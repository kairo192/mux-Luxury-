"""
The shop page is split (apps/storefront/README.md): index.html holds the markup,
src/shop/*.js the code. Keeps it that way and keeps the files wired together.
"""
import re
import unittest
from pathlib import Path

SF = Path(__file__).resolve().parents[2] / "apps" / "storefront"


class TestStorefrontLayout(unittest.TestCase):
    def test_page_has_no_inline_code(self):
        html = (SF / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S)
        inline = [attrs for attrs, body in scripts if body.strip() and "application/ld+json" not in attrs]
        self.assertEqual(inline, [], "shop code belongs in src/shop/, not inline in index.html")
        self.assertIn('<script type="module" src="/src/shop/main.js"></script>', html)
        self.assertNotIn("<style>", html)

    def test_every_shop_file_is_loaded_and_shares_its_functions(self):
        main = (SF / "src" / "shop" / "main.js").read_text(encoding="utf-8")
        for f in sorted((SF / "src" / "shop").glob("*.js")):
            if f.name == "main.js":
                continue
            self.assertIn(f'import "./{f.name}";', main, f.name)
            # onclick="…" handlers and the other files reach the functions through window
            self.assertRegex(f.read_text(encoding="utf-8").rstrip(), r"Object\.assign\(window, \{[\s\S]*\}\);$", f.name)


if __name__ == "__main__":
    unittest.main()
