# Configuration (.env)

All settings of the server and its scripts are read from one `.env` file (on the VPS:
`/opt/luxe/shared/.env`, `chmod 600`). **`backend/app/settings.py` is the single list** of every key: what it is
for, whether production needs it, whether it is secret, its default, and older names still accepted.

| Task | Command (from `backend/`) |
|---|---|
| Make a production file with fresh secrets | `python3 scripts/generate_production_env.py --domain mus-luxury.com --admin-email you@example.com` |
| Check a file (values never printed; exit 1 if a required key is missing) | `python3 -m app.settings check /opt/luxe/shared/.env` |
| See the template | `python3 -m app.settings template production` |
| Regenerate the 4 templates after changing the list | `python3 -m app.settings templates` |

The same check runs **before every deploy** (`release-deploy.sh` stops, changing nothing, if a required key is
missing), is **logged at each start** in production, and is shown to the owner in **CMS → Sauvegardes &
Sécurité → Configuration du serveur** (names and states only — never values).

## What production needs

`APP_ENV`, `PUBLIC_STORE_URL`, `SECRET_KEY`, `CMS_HMAC_SIGNING_SECRET`, `LUXE_DB_ENGINE`, `POSTGRES_PASSWORD`,
`DATABASE_URL`, `BACKUP_ENCRYPTION_KEY` — all written by the generator. Keep `BACKUP_ENCRYPTION_KEY` in a
password manager: without it no backup can be restored.

## Optional (empty = feature off)

| Feature | Keys |
|---|---|
| Off-site copy of the nightly backup (strongly recommended) | `S3_BACKUP_ENABLED=true`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` |
| WhatsApp Cloud API webhook (delivery receipts) | `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` |
| Owner account created at first start instead of the setup screen | `LUXE_SEED_DEMO_ACCOUNTS=1` + `ADMIN_INITIAL_EMAIL`, `ADMIN_INITIAL_FULL_NAME`, `ADMIN_INITIAL_PASSWORD` (12+ characters) |
| Extra domains allowed to call the API | `CORS_ORIGINS` |

Messages to customers on WhatsApp need **no key**: staff send prepared `wa.me` messages from the CMS.

## Not built (no key does anything)

Delivery-company APIs (Yalidine, ZR Express, Maystro), Chargily online payment, e-mail sending (SMTP),
advertising pixels, automatic WhatsApp sending. Older `.env` files may still contain their keys: the check lists
them as "do nothing" — they can be deleted. When one of these features is built, its keys are added to
`settings.py` with the code (a CI test refuses a template key that no code reads, and a key read by the code that
is not in the list).

## Older names still accepted

`CORS_ALLOWED_ORIGINS` → `CORS_ORIGINS`; `MAX_LOGIN_ATTEMPTS_PER_MINUTE` → `LOGIN_ATTEMPTS_PER_MINUTE`;
`WHATSAPP_ACCESS_TOKEN` → `WHATSAPP_CLOUD_API_TOKEN`. (Before this list existed, the first two were silently
ignored.)
