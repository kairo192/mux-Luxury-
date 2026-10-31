# Guide d'Installation & Développement

1. **Backend FastAPI** : `cd backend && pip install -r requirements.txt && python3 -m unittest discover -s tests -v && uvicorn app.main:app --reload --port 8000`
2. **Site Public (`apps/storefront`)** : `cd apps/storefront && npm install && npm run dev`
3. **CMS Bureau Windows (`apps/desktop-cms`)** : `cd apps/desktop-cms && npm install && npm run tauri dev` (ou compilation automatique `.exe` via GitHub Actions `.github/workflows/build-desktop-cms.yml`).
