"""Mus Luxury API: the FastAPI application, its middleware and startup.

The routes themselves live in app/routers/ (one module per area of the shop);
shared helpers in app/common.py, app/deps.py and app/schemas.py."""
from . import config
from . import settings as app_settings
import logging
import re
import secrets
import time
from typing import Dict
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .i18n_messages import localize, request_lang
from fastapi.middleware.cors import CORSMiddleware
from .seed import seed_initial_data
from starlette.middleware.gzip import GZipMiddleware, GZipResponder
from starlette.datastructures import Headers as _Headers


_ENABLE_PUBLIC_DOCS = (not config.is_production()) or app_settings.get("ENABLE_API_DOCS") == "1"


app = FastAPI(
    title="Mus Luxury (LUXE) E-Commerce API",
    version="1.0.0",
    description="Production REST API for LUXE Algerian E-Commerce Storefront & Tauri 2 Desktop CMS",
    docs_url="/api/v1/docs" if _ENABLE_PUBLIC_DOCS else None,
    openapi_url="/api/v1/openapi.json" if _ENABLE_PUBLIC_DOCS else None,
)


@app.exception_handler(StarletteHTTPException)
async def _localized_http_error(request: Request, exc: StarletteHTTPException):
    """Errors in the language of the desktop CMS (X-Luxe-Lang: fr|en|ar).

    Known messages written for people are translated and marked "human"; any
    other request gets exactly what FastAPI would have sent."""
    detail = exc.detail
    body: dict = {"detail": detail}
    lang = request_lang(request.headers.get("x-luxe-lang"))
    if lang and isinstance(detail, str):
        text, known = localize(detail, lang)
        if known:
            body = {"detail": text, "human": True}
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
    "https://mus-luxury.com",
    "https://www.mus-luxury.com",
    "https://api.mus-luxury.com",
]

# CORS_ORIGINS (older name CORS_ALLOWED_ORIGINS, used by earlier .env files).
_EXTRA_CORS = [o.strip() for o in app_settings.get("CORS_ORIGINS").split(",") if o.strip()]

ALLOWED_CORS_ORIGINS = list(dict.fromkeys(_DEFAULT_CORS_ORIGINS + _EXTRA_CORS))



class _LightGZipMiddleware(GZipMiddleware):
    """gzip for JSON/HTML answers over 1000 bytes, sized for a 1-vCPU server.

    - level 6 (as nginx): level 9 costs far more CPU for ~1 % smaller answers;
    - the compressor is always closed (Starlette 0.25 leaves it open for small
      answers: "I/O operation on closed file" in the logs, memory kept longer);
    - file downloads (encrypted backups, up to 100 MB) are sent as they are:
      they cannot be compressed and would only burn the single CPU.
    """

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] == "http"
            and "gzip" in _Headers(scope=scope).get("Accept-Encoding", "")
            and not scope.get("path", "").endswith("/download")
        ):
            responder = GZipResponder(self.app, self.minimum_size, compresslevel=self.compresslevel)
            try:
                await responder(scope, receive, send)
            finally:
                responder.gzip_file.close()
            return
        await self.app(scope, receive, send)



# Compression of API answers over 1000 bytes (catalog, lists, reports).
app.add_middleware(_LightGZipMiddleware, minimum_size=1000, compresslevel=6)



class _RejectNulCharacters:
    """A NUL character (\\u0000) in an address, a query string or a JSON body
    crashed PostgreSQL ("cannot contain NUL"), giving a 500 on public routes —
    e.g. /api/v1/products?category=%00 or an order with "\\u0000" in the name.
    Refused up front with a 422 in French. JSON bodies are small; uploads
    (photos, backups) are never read here."""

    _MESSAGE = b'{"detail":"Caract\xc3\xa8re invalide dans la requ\xc3\xaate."}'

    def __init__(self, app):
        self.app = app

    async def _refuse(self, send):
        await send({"type": "http.response.start", "status": 422,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(self._MESSAGE)).encode())]})
        await send({"type": "http.response.body", "body": self._MESSAGE})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        qs = scope.get("query_string") or b""
        if "\x00" in scope.get("path", "") or b"%00" in qs or b"\x00" in qs:
            return await self._refuse(send)
        ctype = dict(scope.get("headers") or []).get(b"content-type", b"")
        if scope.get("method") in ("POST", "PUT", "PATCH") and ctype.startswith(b"application/json"):
            chunks, more = [], True
            while more:
                message = await receive()
                if message["type"] != "http.request":
                    return await self.app(scope, receive, send)
                chunks.append(message.get("body", b""))
                more = message.get("more_body", False)
            body = b"".join(chunks)
            if b"\x00" in body or b"\\u0000" in body:
                return await self._refuse(send)
            sent = False

            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()
            return await self.app(scope, replay, send)
        return await self.app(scope, receive, send)



app.add_middleware(_RejectNulCharacters)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID", "X-Luxe-Signature", "X-Luxe-Timestamp", "X-Luxe-Nonce", "X-Luxe-Lang"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms", "ETag", "Cache-Control"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start_ns = time.perf_counter_ns()
    incoming_req_id = (request.headers.get("X-Request-ID") or "").strip()
    if incoming_req_id and re.match(r"^[a-zA-Z0-9_\-]{6,64}$", incoming_req_id):
        req_id = incoming_req_id
    else:
        req_id = f"req_{secrets.token_hex(6)}"

    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if not request.url.path.startswith("/api/v1/seo/"):
        # SEO pages are the shop's own HTML: nginx applies the storefront CSP.
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    if request.url.path.startswith("/api/v1/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return response


# ----------------------------------------------------------------------------
# Shared cache for the shop's public lists (1 vCPU / 2 GB VPS).
# Every open shop page asks for the catalogue once a minute; without this,
# each visitor made the server rebuild the whole product list. One answer is
# now computed and served to everyone for at most 5 s, and the cache is
# emptied at once by ANY change (CMS edit, order, till sale...), so the shop
# still shows a new price or a sold-out bag immediately.
# ----------------------------------------------------------------------------
_PUBLIC_CACHE_PATHS = {"/api/v1/products", "/api/v1/categories", "/api/v1/delivery-zones"}

_PUBLIC_CACHE_TTL_S = 5.0

_PUBLIC_CACHE: Dict[str, tuple] = {}

_SKIP_CACHED_HEADERS = {"content-length", "date", "x-request-id", "x-response-time-ms"}



def public_cache_clear() -> None:
    _PUBLIC_CACHE.clear()



@app.middleware("http")
async def public_catalog_cache(request: Request, call_next):
    method = request.method.upper()
    path = request.url.path
    if method != "GET" or path not in _PUBLIC_CACHE_PATHS:
        response = await call_next(request)
        if method in ("POST", "PUT", "PATCH", "DELETE") and path.startswith("/api/v1/"):
            public_cache_clear()
        return response
    gz = "gzip" in (request.headers.get("accept-encoding") or "")
    key = f"{path}?{request.url.query}|{'gz' if gz else 'id'}"
    hit = _PUBLIC_CACHE.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < _PUBLIC_CACHE_TTL_S:
        _, body, headers = hit
        if request.headers.get("if-none-match") and request.headers.get("if-none-match") == headers.get("etag"):
            return Response(status_code=304, headers={"ETag": headers["etag"], "Cache-Control": headers.get("cache-control", "")})
        return Response(content=body, status_code=200, headers=headers)
    response = await call_next(request)
    if response.status_code != 200:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    headers = {k: v for k, v in response.headers.items() if k.lower() not in _SKIP_CACHED_HEADERS}
    if len(_PUBLIC_CACHE) > 200:  # many filter / page combinations: start over
        public_cache_clear()
    _PUBLIC_CACHE[key] = (now, body, headers)
    return Response(content=body, status_code=200, headers=headers)



@app.on_event("startup")
def on_startup():
    seed_initial_data()
    _log_configuration_report()



def _log_configuration_report() -> None:
    """Production: say at start what is missing in .env (values never logged)."""
    if not config.is_production():
        return
    rep = app_settings.public_report()
    log = logging.getLogger("luxe.config")
    for problem in rep["problems"]:
        log.warning("configuration: %s", problem)


# Ensure DB is initialized even when TestClient is instantiated without startup events
seed_initial_data()


# ---------------------------------------------------------------- routes
from .routers import public, auth, reports, catalog, orders, content, webhooks, pos, inventory, system, finance, seo, store  # noqa: E402

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(catalog.router)
app.include_router(orders.router)
app.include_router(content.router)
app.include_router(webhooks.router)
app.include_router(pos.router)
app.include_router(inventory.router)
app.include_router(system.router)
app.include_router(finance.router)
app.include_router(seo.router)
app.include_router(store.router)

# Kept importable from app.main (tests and maintenance scripts use them).
from .routers.catalog import ean_check_digit  # noqa: E402,F401
from .common import _csv_date  # noqa: E402,F401
from .routers.finance import _shop_today  # noqa: E402,F401
from .routers.pos import _client_ts_to_utc_text  # noqa: E402,F401
from .routers.reports import _AUDIT_ACTION_FR, _AUDIT_ENTITY_FR, _shop_day_of, _utc_range_for_days  # noqa: E402,F401
